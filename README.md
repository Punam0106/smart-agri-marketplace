# Smart Agri-Marketplace & Crop Advisory System

A web-based agricultural marketplace and crop advisory platform built with **Python** and **Django** to connect farmers and buyers directly while providing crop guidance, mandi rate tracking, and order management.

## Key Features
- **Farmer & Buyer Accounts:** Role-based registration and login flows for farmers and buyers.
- **Crop Listings:** Farmers can list available crops with pricing and availability details.
- **Orders & Tracking:** Buyers can browse listings and place/track orders.
- **Crop Advisory & Mandi Rates:** Guidance and market rate overview for informed decisions.
- **Admin Management:** Django Admin interface for managing records and oversight.

## Tech Stack
- **Backend & Framework:** Python, Django
- **Frontend:** HTML, CSS, Django Templates
- **Database:** MySQL (used during local development) & SQLite (used in live deployment)
- **Live Demo:** https://punamhavale.pythonanywhere.com

## Local Setup
1. Clone the repository:
   ```bash
   git clone [https://github.com/Punam0106/smart-agri-marketplace.git](https://github.com/Punam0106/smart-agri-marketplace.git)
   cd smart-agri-marketplace
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On Linux/macOS: source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run migrations and start the server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
