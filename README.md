# GitExercise-G05

A Flask web application project with analytics, user & location logging, map, routes to certain locations, AI chatbot and admin dashboard. features.

---

## 📂 Project Structure

```

app/
├── auth.py
├── models.py
├── routes.py
├── admin.py
├── static/
│   ├── style.css
│   └── campus_places.geojson
└── templates/
    ├── admin_dashboard.html
    ├── analytics.html
    ├── edit_locations.html
    ├── edit_user.html
    └── … (other templates)
.gitignore
README.md
requirements.txt

````

---

## 🛠 Features

- User registration, login, role-based access (admin & user)  
- Pageview tracking (which pages users visit)  
- Visit logging for campus locations  
- Admin analytics:  
  - Most visited locations  
  - Page views today  
  - Active users  
  - Dashboard with charts  
- GeoJSON integration: campus places from `campus_places.geojson`  
- Admin UI for importing / editing location data  

---

## ⚙ Setup & Running Locally


3. (Optional) Add environment variables via `.env`:

   ```
   FLASK_ENV=development
   SECRET_KEY=your-secret-key
   MAIL_USERNAME=...
   MAIL_PASSWORD=...
   MAIL_DEFAULT_SENDER=...
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```

To start the Flask application, run the following command in your terminal:


   ```bash
python -m app.app
   ```

   Once the server is running, you can access the website by navigating to http://127.0.0.1:5000/ in your web browser.

---

## 🧮 Analytics & Logging

* **PageView** logs each page visit (endpoint & date).

* **Visit** logs when a user “visits” a campus location (from the GeoJSON).

* `admin/analytics` page displays:

  * Daily page views
  * Most visited locations
  * Active users, etc.

* **Import locations**: you can import campus places from `campus_places.geojson` into the database.

---

## ✅ Tips & Notes

* During development, SQLite is used. Might run into **database locked** errors if many simultaneous writes occur.

---

## License
This project is licensed under the MIT License.