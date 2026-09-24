#!/usr/bin/env bash
set -e
BACKUP_DIR="./backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "بکاپ گیری PROJECT_ROBOTS — Level 5 Autonomous Engineer / Backup PROJECT_ROBOTS — Level 5 Autonomous Engineer to $BACKUP_DIR"
if [ -f .env ]; then cp .env "$BACKUP_DIR/"; echo "✓ .env"; fi
if [ -f docker-compose.yml ]; then
  docker compose ps > "$BACKUP_DIR/ps.txt" 2>&1 || true
  # Backup volumes if possible
  docker run --rm -v $(basename $(pwd))_data:/volume -v $(pwd)/backups:/backup alpine tar czf /backup/$(date +%Y%m%d-%H%M%S)-data.tar.gz -C / volume 2>&1 | head -n 5 || echo "Volume backup skipped (no volume)"
fi
# For file based data
if [ -d data ]; then cp -r data "$BACKUP_DIR/" 2>/dev/null && echo "✓ data/"; fi
if [ -d uploads ]; then cp -r uploads "$BACKUP_DIR/" 2>/dev/null && echo "✓ uploads/"; fi
ls -lh "$BACKUP_DIR"
echo "✓ بکاپ تمام شد / Backup complete: $BACKUP_DIR"
