# Invoice Extraction — Design Spec

**Date :** 2026-04-30
**Scope :** Gmail seulement (extensible aux autres providers plus tard)
**Approche :** Deux phases — scan lecture seule, puis téléchargement ciblé
**Contraintes :** stdlib-only, connexion IMAP unique persistante, zéro modification serveur

---

## Problème

Le comptable demande les factures chaque mois. Actuellement, le système email-archiver classifie et déplace les courriels par headers (From + Subject), mais ne télécharge jamais le contenu ni les pièces jointes. Les factures PDF restent dans Gmail.

## Objectifs

1. Scanner Gmail pour identifier tous les abonnements et factures (rapport d'abonnements)
2. Télécharger les PDFs de factures organisés par mois et fournisseur
3. Générer un CSV récapitulatif par mois pour le comptable

## Non-objectifs

- Extraction automatique de montants depuis les PDFs
- Téléchargement de factures accessibles seulement via liens web
- Modification des courriels sur le serveur (pas de move, delete, ou mark as read)
- Support iCloud/Yahoo (phase future)

---

## Architecture

### Nouveaux fichiers

```
email_archiver/
├── invoice_scanner.py    # Phase 1 : scan lecture seule
├── invoice_downloader.py # Phase 2 : téléchargement + CSV
```

### Fichiers modifiés

```
email_archiver/
├── cli.py                # Ajout sous-commande "invoices" (scan/download)
├── imap_client.py        # Ajout méthode fetch_message()
```

### Fichiers inchangés

```
email_archiver/
├── archiver.py
├── classifier.py
├── organizer.py
├── config.py
├── logging_setup.py
```

### Flot de données

```
CLI "invoices scan gmail"
  -> invoice_scanner.py
    -> IMAPClient.connect()           # connexion unique persistante
    -> IMAPClient.search_all_uids()
    -> Passe 1 : IMAPClient.fetch_headers(uids)  # léger — From + Subject seulement
    -> Classification par patterns (from/subject)
    -> Passe 2 : IMAPClient.fetch_message(uid)    # lourd — seulement les matches
    ->   Vérifie la présence de pièces jointes PDF
    -> Output: reports/gmail-invoices-scan.json + .txt

CLI "invoices download gmail --month 2026-04"
  -> invoice_downloader.py
    -> Lit reports/gmail-invoices-scan.json
    -> IMAPClient.connect()
    -> IMAPClient.fetch_message(uid)  # seulement les UIDs du mois ciblé
    -> Extraction PDFs des pièces jointes MIME
    -> Output: factures/2026-04/<Fournisseur>/YYYY-MM-DD-fichier.pdf
    -> Output: factures/2026-04/recapitulatif.csv
```

---

## Extension de IMAPClient

### Nouvelle méthode : `fetch_message(uid)`

```python
def fetch_message(self, uid: bytes) -> email.message.Message | None:
    """Fetch le message complet (headers + body + attachments).

    Utilise BODY.PEEK[] pour ne PAS marquer le message comme lu.
    Retourne un objet email.message.Message parsé par le stdlib.
    Retourne None si le FETCH échoue.
    """
```

- Commande IMAP : `UID FETCH <uid> (BODY.PEEK[])`
- Parse avec `email.message_from_bytes()` (stdlib `email` module)
- Gestion d'erreurs : FETCH échoue -> log l'erreur, retourne `None`
- Circuit breaker existant (3 erreurs consécutives = STOP) s'applique

Aucune autre modification à IMAPClient. Les méthodes existantes (`fetch_headers`, `archive_uid`, `mark_deleted`, `expunge`) restent intactes.

---

## Invoice Scanner (Phase 1)

### Commande

```bash
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail
```

### Détection de factures

Deux axes de patterns, séparés du classifier existant :

**Par expéditeur :** Dictionnaire `INVOICE_FROM_PATTERNS` — domaines/adresses connus pour envoyer des factures.

**Par sujet :** Liste `INVOICE_SUBJECT_PATTERNS` — regexes compilées :
- `invoice`, `facture`, `receipt`, `reçu`
- `billing`, `payment`, `your bill`
- `relevé`, `statement`, `order confirmation`

Un courriel est une facture si **au moins un** pattern match (from OU subject).

### Mapping fournisseurs

Dictionnaire `PROVIDER_MAP` qui normalise les adresses email vers des noms de dossiers propres :

```python
PROVIDER_MAP = {
    "anthropic": "Anthropic",
    "google.com": "Google",
    "xplore.ca": "Xplore",
    "staples": "BureauEnGros",
    "greengeeks": "GreenGeeks",
    "telus": "Telus",
    "aquavoice": "AquaVoice",
    "fal.ai": "Fal",
}
```

- Fournisseur connu -> nom du dictionnaire
- Fournisseur inconnu -> nom dérivé du domaine email (ex. `billing@newservice.io` -> `Newservice`)
- Le rapport signale les fournisseurs inconnus pour ajustement manuel

### Données extraites par courriel

Pour chaque courriel identifié comme facture :
- UID
- Expéditeur (adresse brute + nom fournisseur normalisé)
- Date du courriel (header `Date:`)
- Sujet
- Présence de PDF attaché (oui/non)
- Nom et taille du fichier PDF si présent
- Indication lien-seulement si pas de PDF mais contenu HTML avec lien

### Output

**`reports/gmail-invoices-scan.json`** — données structurées :

```json
{
  "scan_date": "2026-04-30",
  "account": "gmail",
  "total_emails_scanned": 1200,
  "invoices_found": 87,
  "providers": {
    "Anthropic": {
      "count": 6,
      "has_pdf_attachments": true,
      "months": ["2025-11", "2025-12", "2026-01"]
    },
    "Google": {
      "count": 12,
      "has_pdf_attachments": false,
      "link_only": true,
      "months": ["2025-10", "2025-11"]
    }
  },
  "invoices": [
    {
      "uid": "4532",
      "from": "billing@anthropic.com",
      "provider": "Anthropic",
      "subject": "Your March invoice",
      "date": "2026-03-01",
      "has_pdf": true,
      "pdf_filename": "invoice-2026-03.pdf",
      "pdf_size_bytes": 45230
    }
  ]
}
```

**`reports/gmail-invoices-scan.txt`** — résumé lisible :

```
=== Scan des factures — Gmail ===
Date du scan : 2026-04-30
Courriels scannés : 1200
Factures trouvées : 87

ABONNEMENTS IDENTIFIÉS :
  Anthropic        6 factures  [PDF]
  Google Workspace 12 factures [LIEN]
  Xplore           8 factures  [PDF]
  Telus            5 factures  [PDF]

SANS PDF (à télécharger manuellement) :
  Google Workspace — liens dans les courriels
```

### Stratégie deux passes (optimisation critique)

**Passe 1 — Headers seulement :** Utilise `fetch_headers()` existant (léger, From + Subject) sur tous les UIDs de l'inbox, en lots de 50 (comme l'archiveur). Classifie par patterns. Typiquement, seule une fraction des courriels sont des factures.

**Passe 2 — Messages complets :** Seulement pour les courriels identifiés comme factures en Passe 1. Utilise `fetch_message()` (lourd) en lots de 25, pour vérifier la présence de pièces jointes PDF et extraire leurs métadonnées.

Ceci évite de télécharger le corps complet de milliers de courriels non pertinents.

---

## Invoice Downloader (Phase 2)

### Commande

```bash
# Mois spécifique
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04

# Mois courant (défaut)
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail
```

### Prérequis

Le scan doit exister (`reports/gmail-invoices-scan.json`). Si absent, message d'erreur clair : « Exécute `invoices scan gmail` d'abord ».

### Structure de sortie

```
factures/
└── 2026-04/
    ├── Anthropic/
    │   └── 2026-04-01-invoice.pdf
    ├── Telus/
    │   └── 2026-04-15-facture-telus.pdf
    ├── Xplore/
    │   └── 2026-04-08-invoice-xplore.pdf
    └── recapitulatif.csv
```

### Nommage des PDFs

- Format : `YYYY-MM-DD-nom-original.pdf`
- Date : extraite du header `Date:` du courriel
- Nom original : `filename` de la pièce jointe MIME
- Si nom générique (`invoice.pdf`, `document.pdf`) : préfixé avec le fournisseur en minuscules (`2026-04-01-anthropic-invoice.pdf`)

### CSV récapitulatif

Fichier : `factures/2026-04/recapitulatif.csv`

```csv
date,fournisseur,sujet,fichier_pdf,source_email
2026-04-01,Anthropic,Your March invoice,2026-04-01-invoice.pdf,billing@anthropic.com
2026-04-08,Xplore,Your bill is ready,2026-04-08-invoice-xplore.pdf,billing@xplore.ca
2026-04-15,Telus,Votre facture,2026-04-15-facture-telus.pdf,factures@telus.com
```

- Courriels sans PDF : ligne incluse avec `fichier_pdf` vide + log `[NO-PDF]`
- Encodage : UTF-8 avec BOM (compatibilité Excel)

### Gestion des cas limites

| Cas | Comportement |
|-----|-------------|
| Pas de scan existant | Erreur : « Exécute `invoices scan gmail` d'abord » |
| PDF déjà téléchargé (même nom, même taille) | Skip avec log `[SKIP]` |
| Courriel sans PDF (lien seulement) | Ligne CSV avec `fichier_pdf` vide, log `[NO-PDF]` |
| Plusieurs PDFs dans un même courriel | Tous téléchargés dans le même dossier fournisseur |
| Aucune facture trouvée pour le mois | Message informatif, pas d'erreur |

---

## CLI

### Nouvelles commandes

```bash
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail  # mois courant
```

### Intégration dans cli.py

`invoices` est une sous-commande avec deux actions (`scan`, `download`), même style que `archive`, `preview`, `organize`, `stats`.

L'argument `--month` est optionnel pour `download`, défaut = mois courant (`YYYY-MM`).

---

## Sécurité et fiabilité

- **Connexion unique persistante** — même modèle que le reste du codebase
- **BODY.PEEK[]** — ne modifie jamais le flag `\Seen`
- **Circuit breaker** — 3 erreurs FETCH consécutives = arrêt complet
- **Aucune écriture serveur** — pas de COPY, STORE, DELETE, EXPUNGE
- **Credentials via Keychain** — jamais en clair
- **Pas de retry automatique** — cohérent avec les invariants du projet
- **Écriture atomique** — les fichiers JSON/CSV sont écrits via tmp+rename

## Dépendances

Aucune nouvelle dépendance. Modules stdlib utilisés :
- `email` / `email.policy` — parsing MIME des messages complets
- `email.header` — décodage des headers encodés (déjà utilisé dans imap_client.py)
- `csv` — génération du récapitulatif
- `json` — sérialisation du scan
- `base64` — décodage des pièces jointes (géré par `email` module)
- `mimetypes` — identification des types de fichiers
- `datetime` — parsing des dates de courriels
