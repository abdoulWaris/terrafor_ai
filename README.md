# tfai-localstack-lab

Mini-lab pour piloter Terraform en langage naturel via un LLM local (Ollama),
en testant l'infra générée contre LocalStack (AWS simulé en local).

```
[ toi ] --langage naturel--> [ tfai (CLI Python) ] --prompt--> [ Ollama ]
                                     |                              |
                                     | <---- bloc HCL généré -------+
                                     v
                              terraform/main.tf  --terraform apply-->  LocalStack
```

## Stack

- **Ollama** : exécute le LLM en local (`llama3.1`, `qwen2.5-coder`, `mistral`, ...)
- **tfai** : CLI Python (Click) qui :
  - construit le prompt avec le contenu actuel de `main.tf` comme contexte
  - extrait le bloc HCL renvoyé par le modèle
  - le **fusionne par bloc** (`resource`/`data`/`variable`/`output`, identifié
    par type + nom) dans `main.tf`, sans écraser le reste du fichier
  - lance `terraform fmt` puis `terraform validate`
  - te montre un **diff** avant d'écrire quoi que ce soit
- **Terraform** : tu gardes 100% le contrôle (`plan`/`apply`/`destroy` restent
  des commandes explicites)
- **LocalStack** : simule S3, DynamoDB, SQS, SNS, Lambda, IAM, EC2, etc. sur
  `http://localhost:4566`

## Prérequis

- Docker + Docker Compose
- Terraform CLI installé (tu maîtrises déjà)
- Python 3.9+
- Ollama installé en natif (recommandé, surtout si tu as un GPU) :
  https://ollama.com

## Installation

```bash
# 1. Démarrer LocalStack (et éventuellement Ollama en conteneur)
docker compose up -d localstack
# Si Ollama est natif sur l'hôte, pas besoin du service "ollama" du compose.

# 2. Récupérer un modèle (à faire une seule fois)
ollama pull llama3.1
# Alternative plus orientée code : ollama pull qwen2.5-coder

# 3. Installer la CLI tfai
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Initialisation du workspace Terraform

```bash
tfai init
```

Cela crée (si absent) :
- `terraform/provider.tf` : provider AWS configuré avec les endpoints
  LocalStack (`http://localhost:4566`, credentials factices `test`/`test`)
- `terraform/main.tf` : fichier vide géré par tfai
- lance `terraform init`

## Utilisation

### Une instruction à la fois

```bash
tfai ask "crée un bucket S3 nommé uploads avec versioning activé"
```

tfai va :
1. envoyer le contenu actuel de `main.tf` + ta demande au modèle
2. afficher le **diff** proposé
3. te demander confirmation avant d'écrire
4. lancer `terraform fmt` + `terraform validate`

Ensuite :

```bash
tfai plan      # voir ce que terraform ferait sur LocalStack
tfai apply -y  # appliquer réellement (sur LocalStack, donc sans risque)
```

### Itérer sur la même ressource

```bash
tfai ask "ajoute une règle de cycle de vie qui supprime les objets après 30 jours sur le bucket uploads"
```

Comme le prompt envoie l'état actuel de `main.tf`, le modèle est instruit
pour **réécrire le bloc complet** `resource "aws_s3_bucket" "uploads"` avec
le même nom logique → tfai remplace l'ancien bloc par le nouveau plutôt que
d'en créer un doublon.

### Mode conversationnel

```bash
tfai chat
```

```
> crée une table DynamoDB "sessions" avec une clé de partition "session_id" en string
[diff + confirmation...]
> ajoute un index secondaire global sur l'attribut "user_id"
[diff + confirmation...]
> plan
> apply
```

### Autres commandes

```bash
tfai show            # affiche le main.tf actuel
tfai models          # liste les modèles Ollama disponibles
tfai destroy -y       # détruit les ressources sur LocalStack
```

### Options globales

```bash
tfai --model qwen2.5-coder ask "..."   # changer de modèle
tfai --dir terraform ask "..."         # changer de répertoire (par défaut: terraform/)
```

Variables d'environnement équivalentes : `TFAI_MODEL`, `TFAI_DIR`, `OLLAMA_HOST`.

## Limites volontaires (pour un lab)

- tfai ne génère que des blocs `resource` / `data` / `variable` / `output` ; le
  `provider.tf` reste géré à la main (un seul endroit, pas de risque que le
  LLM casse la connexion à LocalStack).
- La fusion est basée sur **type + nom logique** du bloc, pas sur une analyse
  sémantique complète du HCL — pour un usage perso/lab c'est largement
  suffisant, mais ne remplace pas une vraie review pour un projet en équipe.
- Aucune commande destructive (`apply`, `destroy`) n'est lancée
  automatiquement par `tfai ask` : tu gardes la main.

## Idées d'évolution

- Ajouter un sous-répertoire par "stack" (`tfai --dir stacks/vpc ask ...`)
- Détecter les ressources non supportées par LocalStack (selon l'edition
  utilisée) et avertir l'utilisateur
- Ajouter `tfai explain` qui demande au LLM de résumer en français le contenu
  actuel de `main.tf`
- Historiser les prompts/diffs dans un fichier `.tfai/history.jsonl`
