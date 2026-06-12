# terrafor_ai
Voici une version **ultra minimaliste** prête à copier-coller dans un `README.md` :

````md
# LLM + Terraform + LocalStack Lab

Projet local combinant :
- un LLM local (Ollama)
- un CLI Python (tfai)
- Terraform
- LocalStack (AWS local)

## Objectif

Générer de l’infrastructure avec un LLM et la tester en local sans cloud réel.

## Stack

- Ollama (LLM local)
- Terraform
- Docker + LocalStack
- Python CLI

## Usage

### 1. Lancer le LLM
```bash
ollama run llama3
````

### 2. Lancer LocalStack

```bash
cd localstack
docker compose up -d
```

### 3. Générer du Terraform

```bash
python cli/tfai.py "create s3 bucket"
```

### 4. Appliquer Terraform

```bash
cd infra
terraform init
terraform apply
```

## Structure

```
cli/        -> CLI tfai
infra/      -> Terraform généré
localstack/ -> environnement AWS local
```

## Note

Projet local de test, aucune ressource cloud réelle utilisée.

```

---

Si tu veux, demain on peut :
- rendre le CLI propre (commande `tfai`)
- ajouter LocalStack + AWS provider clean
- ou faire un mode interactif type chat 👍
```
