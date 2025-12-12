from flask import Flask, render_template, request, redirect, url_for
import re
import sqlite3

app = Flask(__name__)
DB = "songs.db"

# -------------------------------
# Chord transposition logic
# -------------------------------

NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F",
               "F#", "G", "G#", "A", "A#", "B"]

NOTES_FLAT = ["C", "Db", "D", "Eb", "E", "F",
              "Gb", "G", "Ab", "A", "Bb", "B"]

CHORD_REGEX = re.compile(r'\(([A-G][#b]?(?:m|maj7|m7|sus4|sus2|dim|aug|7)?)\)')

def transpose_root(root, steps):
    if len(root) > 1 and root[1] in "#b":
        base = root[:2]
        suffix = root[2:]
    else:
        base = root[:1]
        suffix = root[1:]

    if base in NOTES_SHARP:
        idx = NOTES_SHARP.index(base)
    else:
        idx = NOTES_FLAT.index(base)

    new_idx = (idx + steps) % 12
    new_base = NOTES_SHARP[new_idx]
    return new_base + suffix

def transpose_text(text, steps):
    def replace_chord(match):
        chord = match.group(1)
        new_chord = transpose_root(chord, steps)
        return f"({new_chord})"
    return CHORD_REGEX.sub(replace_chord, text)

# -------------------------------
# Database functions
# -------------------------------

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    content TEXT,
                    capo INTEGER DEFAULT 0
                )""")
    # Ensure capo and name exist
    c.execute("PRAGMA table_info(songs)")
    columns = [col[1] for col in c.fetchall()]
    if "capo" not in columns:
        c.execute("ALTER TABLE songs ADD COLUMN capo INTEGER DEFAULT 0")
    if "name" not in columns:
        c.execute("ALTER TABLE songs ADD COLUMN name TEXT")
    conn.commit()
    conn.close()

def save_song(name, content, capo):
    name = name.title()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name FROM songs where name=?", (name,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return
    c.execute("INSERT INTO songs (name, content, capo) VALUES (?, ?, ?)", (name, content, capo))
    conn.commit()
    conn.close()

def delete_song(song_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM songs WHERE id=?", (song_id,))
    conn.commit()
    conn.close()

def get_songs():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, name, content, capo FROM songs ORDER BY id DESC")
    songs = c.fetchall()
    conn.close()
    return songs

def get_song_by_id(song_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name, content, capo FROM songs WHERE id=?", (song_id,))
    song = c.fetchone()
    conn.close()
    if song:
        return song[0], song[1], song[2]
    return "", "", 0

# def update_song(song_id, ):

# -------------------------------
# Routes
# -------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    input_text = ""
    output_text = ""
    capo = 0
    name = ""
    songs = get_songs()

    song_id = request.args.get("song_id")
    if song_id:
        name, input_text, capo = get_song_by_id(song_id)

    if request.method == "POST":
        input_text = request.form.get("songtext") or request.form.get("output_text")
        capo = int(request.form.get("capo", 0))
        name = request.form.get("name", "")
        action = request.form["action"]

        if action == "up":
            steps = 1
        elif action == "down":
            steps = -1
        elif action == "save":
            save_song(name, request.form.get("output_text") or request.form.get("songtext"), capo)
            return redirect(url_for('index'))
        elif action.startswith("delete_"):
            song_to_delete = int(action.split("_")[1])
            delete_song(song_to_delete)
            return redirect(url_for('index'))
        elif action == "new":
            input_text = ""
            output_text = ""
            capo = 0
            name = ""
            steps = 0
        else:
            steps = 0

        output_text = transpose_text(input_text, steps)
        capo = (capo - steps) % 12
        input_text = output_text

    return render_template("index_v2.html",
                           input_text=input_text,
                           output_text=output_text,
                           capo=capo,
                           name=name,
                           songs=songs)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", debug=True)
