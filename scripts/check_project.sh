#!/usr/bin/env bash
set -e

PROJECT_DIR="$HOME/seedance_gui"
cd "$PROJECT_DIR"

echo "PROJECT_DIR=$PROJECT_DIR"
echo "PWD=$(pwd)"
echo

echo "Python:"
.venv/bin/python --version
echo

echo "Folders:"
for p in app data outputs logs scripts sample_project; do
  if [ -d "$p" ]; then
    echo "OK: $p"
  else
    echo "MISSING: $p"
  fi
done
echo

echo "Files:"
for f in requirements.txt .env.example .env .gitignore README.md app/settings.py; do
  if [ -f "$f" ]; then
    echo "OK: $f"
  else
    echo "MISSING: $f"
  fi
done
echo

echo "Output folder:"
if [ -d "/mnt/c/AI_OUTPUT/Example_project" ]; then
  echo "OK: /mnt/c/AI_OUTPUT/Example_project"
else
  echo "MISSING: /mnt/c/AI_OUTPUT/Example_project"
fi
