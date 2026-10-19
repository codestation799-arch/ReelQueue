# ReelQueue — Movie Ticket Booking Website (Python)

A student-friendly Flask website demonstrating movie booking, SQLite storage, and a FIFO waiting queue.

## Requirements
- Python 3.10 or newer
- Internet is optional for the app itself. Google Fonts only affect typography.

## Run in VS Code (Windows)
1. Extract the ZIP into a folder, for example `movie_ticket_queue_website`.
2. Open that folder in VS Code: **File → Open Folder**.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment (recommended):
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use Command Prompt terminal and run:
   ```bat
   .venv\Scripts\activate.bat
   ```
5. Install Flask:
   ```powershell
   py -m pip install flask
   ```
6. Start the website:
   ```powershell
   py app.py
   ```
7. Open the local address printed in the terminal, usually `http://127.0.0.1:5000`.

## How to demonstrate the queue
- Each movie and showtime has a demo capacity of **5 seats**.
- Make bookings until a show reaches 5 confirmed seats.
- Any extra booking for that exact movie and showtime is placed into the waiting queue.
- Open **Waiting queue** to show the FIFO order.
- Cancel a confirmed booking from **Bookings**. The first waiting request that fits in the available seats is promoted.

## Project structure
- `app.py` — Flask routes, queue logic, and SQLite operations
- `templates/index.html` — movie listings and booking form
- `templates/bookings.html` — bookings dashboard and cancellations
- `templates/queue.html` — waiting queue display
- `static/style.css` — responsive dark-themed design
- `bookings.db` — created automatically when you run the app

## Important notes
- This is a local classroom demo, not a production ticketing service.
- It does not process real payments or reserve real cinema seats.
- The waiting queue uses Python `collections.deque`; booking records persist in SQLite.
- Before deploying publicly, change `secret_key`, turn off Flask debug mode, add validation/security controls, and handle concurrent bookings transactionally.
