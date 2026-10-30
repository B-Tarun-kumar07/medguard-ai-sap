MedGuard AI
A hackathon prototype for resilient hospital medicine supply chains. It helps teams review medicine inventory, spot shortages, simulate supply disruptions, review proposed actions, and track shipments.
Demo only: Hospitals, medicines, inventory, dates, suppliers, and shipments are sample data. The app is not connected to live hospital, supplier, carrier, or SAP systems. It is not a medical system.

Features
- Inventory view with manufacture and expiry dates marked as sample data
- Low stock and out of stock alerts
- Pharmacy orders and shipment status tracking
- Simulated supply disruption scenarios and recommendations
- Human review for proposed actions
- Audit history and admin stock and sales workbook download
Run locally
Requirements: Python 3.10+ and Node.js.
1. Extract the project ZIP and open a terminal in the medguard-ai folder.
2. Install backend dependencies:
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
3. Start the backend in one terminal:
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
4. In another terminal, install and start the frontend:
   npm install
   npm run dev
5. Open the local address printed by the frontend, usually http://127.0.0.1:5173.
