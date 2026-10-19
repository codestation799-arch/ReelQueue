from flask import Flask, render_template, request, redirect, url_for, flash
from collections import deque
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "change-this-secret-key-for-a-real-deployment"
DB_PATH = os.path.join(os.path.dirname(__file__), "bookings.db")

# Queue for customers waiting when a show is sold out.
# The database persists bookings; this deque is rebuilt from the waiting-list table at startup.
waiting_queues = {}

MOVIES = [
    {"id": "stellar", "title": "Interstellar", "genre": "Sci-Fi • Adventure", "duration": "2h 49m", "price": 180, "emoji": "🚀", "description": "A journey beyond the stars."},
    {"id": "dragon", "title": "Dragon Warrior", "genre": "Action • Fantasy", "duration": "2h 12m", "price": 160, "emoji": "🐉", "description": "A hero rises when the world needs one."},
    {"id": "city", "title": "Midnight in the City", "genre": "Thriller • Drama", "duration": "1h 58m", "price": 140, "emoji": "🌃", "description": "One night. One secret. No way back."},
]
SHOWS = ["12:30 PM", "3:45 PM", "7:00 PM", "10:15 PM"]
SEATS_PER_SHOW = 5  # Kept small so the waiting queue is easy to demonstrate in a college project.

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                movie_id TEXT NOT NULL,
                show_time TEXT NOT NULL,
                seats INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
    rebuild_queues()

def queue_key(movie_id, show_time):
    return f"{movie_id}|{show_time}"

def rebuild_queues():
    global waiting_queues
    waiting_queues = {}
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT id, movie_id, show_time FROM bookings WHERE status='Waiting' ORDER BY id"
        ).fetchall()
    for row in rows:
        key = queue_key(row["movie_id"], row["show_time"])
        waiting_queues.setdefault(key, deque()).append(row["id"])

def movie_by_id(movie_id):
    return next((m for m in MOVIES if m["id"] == movie_id), None)

def show_booked_count(movie_id, show_time):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(seats), 0) AS total FROM bookings "
            "WHERE movie_id=? AND show_time=? AND status='Confirmed'",
            (movie_id, show_time)
        ).fetchone()
    return int(row["total"])

def queue_for(movie_id, show_time):
    return waiting_queues.setdefault(queue_key(movie_id, show_time), deque())

@app.route("/")
def index():
    movie_cards = []
    for movie in MOVIES:
        movie_cards.append({**movie, "shows": SHOWS})
    return render_template("index.html", movies=movie_cards)

@app.route("/book", methods=["POST"])
def book():
    name = request.form.get("customer_name", "").strip()
    movie_id = request.form.get("movie_id", "")
    show_time = request.form.get("show_time", "")
    try:
        seats = int(request.form.get("seats", "1"))
    except ValueError:
        seats = 0

    movie = movie_by_id(movie_id)
    if not name or len(name) > 80:
        flash("Please enter a name (up to 80 characters).", "error")
        return redirect(url_for("index"))
    if not movie or show_time not in SHOWS or not 1 <= seats <= 5:
        flash("Please choose a valid movie, showtime, and 1–5 seats.", "error")
        return redirect(url_for("index"))

    booked = show_booked_count(movie_id, show_time)
    status = "Confirmed" if booked + seats <= SEATS_PER_SHOW else "Waiting"
    created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

    with connect_db() as conn:
        cur = conn.execute(
            "INSERT INTO bookings (customer_name, movie_id, show_time, seats, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, movie_id, show_time, seats, status, created_at)
        )
        booking_id = cur.lastrowid

    if status == "Waiting":
        queue_for(movie_id, show_time).append(booking_id)
        flash(f"Show is full. You are #{len(queue_for(movie_id, show_time))} in the waiting queue. Booking ID: #{booking_id}", "wait")
    else:
        flash(f"Booking confirmed for {name}! Booking ID: #{booking_id}. Total: ₹{movie['price'] * seats}.", "success")
    return redirect(url_for("bookings"))

@app.route("/bookings")
def bookings():
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM bookings ORDER BY id DESC LIMIT 100").fetchall()
    items = []
    for row in rows:
        movie = movie_by_id(row["movie_id"])
        items.append({
            "id": row["id"],
            "name": row["customer_name"],
            "movie": movie["title"] if movie else row["movie_id"],
            "emoji": movie["emoji"] if movie else "🎬",
            "show_time": row["show_time"],
            "seats": row["seats"],
            "status": row["status"],
            "created_at": row["created_at"],
            "total": (movie["price"] * row["seats"]) if movie else 0,
        })
    return render_template("bookings.html", bookings=items)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id):
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if not row or row["status"] != "Confirmed":
            flash("Only confirmed bookings can be cancelled.", "error")
            return redirect(url_for("bookings"))

        movie_id, show_time, seats = row["movie_id"], row["show_time"], row["seats"]
        conn.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))

        # Promote the first waiting customer whose entire seat request can be fulfilled.
        q = queue_for(movie_id, show_time)
        while q:
            next_id = q[0]
            next_row = conn.execute("SELECT * FROM bookings WHERE id=?", (next_id,)).fetchone()
            if not next_row or next_row["status"] != "Waiting":
                q.popleft()
                continue
            current = conn.execute(
                "SELECT COALESCE(SUM(seats), 0) AS total FROM bookings "
                "WHERE movie_id=? AND show_time=? AND status='Confirmed'",
                (movie_id, show_time)
            ).fetchone()["total"]
            if current + next_row["seats"] <= SEATS_PER_SHOW:
                q.popleft()
                conn.execute("UPDATE bookings SET status='Confirmed' WHERE id=?", (next_id,))
                flash(f"Booking #{booking_id} cancelled. Waiting customer {next_row['customer_name']} (#{next_id}) has been promoted to Confirmed.", "success")
            else:
                flash(f"Booking #{booking_id} cancelled. The first waiting request needs more seats than are currently free, so the queue remains in order.", "wait")
            break
        else:
            flash(f"Booking #{booking_id} cancelled.", "success")

    rebuild_queues()
    return redirect(url_for("bookings"))

@app.route("/queue")
def queue_page():
    queue_rows = []
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM bookings WHERE status='Waiting' ORDER BY id").fetchall()
    for row in rows:
        movie = movie_by_id(row["movie_id"])
        queue_rows.append({
            "id": row["id"], "name": row["customer_name"],
            "movie": movie["title"] if movie else row["movie_id"],
            "show_time": row["show_time"], "seats": row["seats"]
        })
    return render_template("queue.html", queue=queue_rows, capacity=SEATS_PER_SHOW)

@app.route("/reset-demo", methods=["POST"])
def reset_demo():
    with connect_db() as conn:
        conn.execute("DELETE FROM bookings")
    rebuild_queues()
    flash("Demo bookings cleared.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
