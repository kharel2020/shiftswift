#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
echo "Building CloudPanel zips..."
python3 scripts/build_cloudpanel_zips.py
if [ $? -eq 0 ]; then
  echo ""
  echo "Done. Upload these files to Hostinger:"
  ls -lh deploy/cloudpanel/dist/*.zip
  open deploy/cloudpanel/dist
else
  echo "Build failed."
  read -p "Press Enter to close..."
fi
