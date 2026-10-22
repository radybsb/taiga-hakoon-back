# Hakoon source snapshot

This is the customized source snapshot used to start the Hakoon repositories.
Upstream licenses, copyright notices and contributor lists are preserved.
Runtime secrets, generated development output and the original Git history are excluded.
The original local repositories remain unchanged.

Pushes to develop and manual runs run `.github/workflows/image.yml`; successful pushes publish
tested GHCR images tagged with the full commit SHA and a unique run/attempt suffix. Pull requests build/test only.
Production is not automatically updated by this workflow.

Deployment, isolated homolog installation, credentials and recovery are documented at:
https://github.com/radybsb/taiga-hakoon-docker/blob/main/HAKOON-DEPLOYMENT.md

Use the new repository checkout for ongoing work; changes in the old local folders
are not synchronized automatically.
