#!/bin/bash
set -e
# --season "$SEASON" \

for SEASON in $(seq 2011 2015); do
  uvrm scrape_games nfl \
    --creds creds.json \
    --headless \
    --season "$SEASON" \
    --min-week 1 \
    --max-week 18 \
    --season-type "REG" \
    --store-db
done