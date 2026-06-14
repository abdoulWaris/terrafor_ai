# Géré par tfai
# Ce fichier est généré/modifié automatiquement à partir des instructions
# envoyées au LLM via `tfai ask "..."` ou `tfai chat`.
# Vous pouvez aussi l'éditer manuellement, tfai fusionnera ses ajouts par
# bloc (resource/data/variable/output) en se basant sur le type + le nom.

resource "aws_s3_bucket" "example_bucket" {
  bucket = "mon-bucket-12345"
  acl    = "private"

  # Pour supprimer le bucket, commentez la ressource et effectuez ensuite manuellement : terraform destroy
}
