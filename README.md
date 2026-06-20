# 🏨 Booking Hotels

A modern, responsive, and fully-featured Hotel Booking Web Application built with **Flask (Python)** and **MySQL**. This application provides a seamless experience for both customers (to browse and book rooms) and administrators (to manage hotel inventory, rooms, and bookings).

## ✨ Features

### 👤 Customer Facing
*   **Dynamic Location Filter:** Easily find hotels based on Provinces and Cities across Indonesia.
*   **Multiple Image Galleries:** View beautiful hotel and room images through intuitive, modern Carousel/Slider UI.
*   **Real-time Availability:** Smart filtering logic ensures you only see rooms that are available for your selected check-in and check-out dates.
*   **Waiting List / Booking System:** Secure a room or join a waiting list if rooms are currently occupied.
*   **OAuth / Traditional Authentication:** Secure user registration and login system.

### 🛡️ Admin Dashboard (MVP)
*   **Inventory Management:** Add new hotels and rooms easily.
*   **Modal Quick-Edit:** Edit hotel and room details instantly via pop-up modals without page reloads.
*   **Advanced Image Handling:** Support for multiple image uploads per hotel and room. The backend automatically cleans up physical junk files when old images are replaced.
*   **Booking Supervision:** View recent bookings, revenue, and cancel bookings if necessary.

---

## 🛠️ Technology Stack

*   **Backend:** Python 3.x, Flask, Flask-Session
*   **Database:** MySQL (via `mysql-connector-python`)
*   **Frontend:** HTML5, Vanilla CSS (Modern Design System with CSS Variables), Vanilla JavaScript (AJAX/Fetch API for dynamic locations)
*   **Environment Management:** `python-dotenv`

---

## 🚀 Getting Started

Follow these instructions to set up the project locally on your machine.

### 1. Prerequisites
*   [Python 3.8+](https://www.python.org/downloads/)
*   [MySQL Server](https://dev.mysql.com/downloads/mysql/) (XAMPP/Laragon is also fine)
*   Virtual Environment module (`venv`)

### 2. Installation Steps

1. **Clone or Open the Repository:**
   ```bash
   cd booking-hotels
   ```

2. **Set up Virtual Environment:**
   ```bash
   python -m venv venv
   # Activate it (Windows):
   .\venv\Scripts\activate
   # Activate it (Mac/Linux):
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   Make sure you install the required packages (e.g., `flask`, `mysql-connector-python`, `python-dotenv`, `flask-session`).
   *(If you have a `requirements.txt`, run `pip install -r requirements.txt`)*

4. **Database Configuration:**
   * Create a MySQL database named `hotel_booking` (or according to your preference).
   * Copy the `.env.example` file to `.env` (if available) or create a new `.env` file in the root directory.
   * Add your database credentials:
     ```env
     DB_HOST=localhost
     DB_USER=root
     DB_PASSWORD=
     DB_NAME=hotel_booking
     SECRET_KEY=your_super_secret_key
     ```

5. **Run Migrations / Initialize DB:**
   Run the initialization scripts to create the necessary tables (`users`, `hotels`, `rooms`, `hotel_images`, `room_images`, `provinces`, `cities`, `bookings`).
   ```bash
   python init_db.py
   python update_db_images.py
   ```

### 3. Running the Application

Once everything is set up, start the development server:

```bash
python app.py
```

The application should now be running. Open your browser and navigate to:
**`http://localhost:5000`**

---

## 📂 Project Structure

```text
booking-hotels/
├── app.py                   # Main application entry point
├── db.py                    # Database connection helpers
├── utils.py                 # Helper functions (File uploads, cleanup, auth wrappers)
├── routes/                  # Route definitions (Blueprints)
│   ├── auth.py              # Authentication routes
│   ├── main.py              # Public facing routes (Home, Search)
│   ├── admin.py             # Admin Dashboard logic
│   └── booking.py           # Booking transaction logic
├── static/                  # Static assets (CSS, JS, Images)
│   ├── css/
│   │   └── style.css        # Main stylesheet
│   └── uploads/             # Directory for uploaded hotel/room images
└── templates/               # HTML templates (Jinja2)
    ├── admin/               # Admin dashboard views
    └── ...                  # Public pages (index, rooms, about, etc.)
```

---
