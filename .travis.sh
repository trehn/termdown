#!/bin/sh -e

if [ -z "$SNAPCRAFT_SECRET" ]; then
    exit 1
fi

mkdir -p ".encrypted"
if [ ! -e ".encrypted/snapcraft.cfg.enc" ]; then
    echo "Seeding a new macaroon."
    echo "$SNAPCRAFT_CONFIG" > ".encrypted/snapcraft.cfg.enc"
fi

mkdir -p "$HOME/.config/snapcraft"
openssl enc -aes-256-cbc -base64 -pass env:SNAPCRAFT_SECRET \
    -d -in ".encrypted/snapcraft.cfg.enc" \
    -out "$HOME/.config/snapcraft/snapcraft.cfg"

if docker run -v "$HOME:/root" -v "$(pwd):/cwd snapcore/snapcraft" sh -c 'cd /cwd; snapcraft'; then
    if [ "${TRAVIS_BRANCH}" = "master" ]; then
        docker run -v "$HOME:/root" -v "$(pwd):/cwd snapcore/snapcraft" sh -c "cd /cwd; snapcraft push *.snap --release edge"
    fi
fi

openssl enc -aes-256-cbc -base64 -pass env:SNAPCRAFT_SECRET -out ".encrypted/snapcraft.cfg.enc" < "$HOME/.config/snapcraft/snapcraft.cfg"
rm -f "$HOME/.config/snapcraft/snapcraft.cfg"
