# ShiftSwift HR — Frontend install (CloudPanel Static HTML site)

Upload **shiftswifthr-frontend.zip** for **app.shiftswifthr.co.uk** and **www.shiftswifthr.co.uk**.

## app.shiftswifthr.co.uk (admin + employee portal)

1. Create **Static HTML Site** in CloudPanel for `app.shiftswifthr.co.uk`
2. Upload zip to site root and extract:

```bash
cd /home/<user>/htdocs/app.shiftswifthr.co.uk
unzip -o shiftswifthr-frontend.zip
```

3. Document root must contain `index.html`, `admin.html`, `business-login.html`, `assets/`, etc.  
   If zip created a `frontend/` folder, move contents up:

```bash
mv frontend/* . && rmdir frontend
```

4. Enable SSL in CloudPanel
5. Open `https://app.shiftswifthr.co.uk/business-login.html`

## www.shiftswifthr.co.uk (marketing)

Same zip — extract into www site root. Uses the same `frontend/` files (`index.html` is the marketing home).

## API URL

Production API is already set in `brand-config.js` to `https://api.shiftswifthr.co.uk`.  
Ensure the API site is live before testing login.
