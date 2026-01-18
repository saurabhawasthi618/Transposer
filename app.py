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

def extract_first_chord(text):
    """Extract the first chord from text using CHORD_REGEX"""
    match = CHORD_REGEX.search(text)
    if match:
        return match.group(1)
    return ""

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
                    capo INTEGER DEFAULT 0,
                    key TEXT DEFAULT ''
                )""")
    # Ensure capo and name exist
    c.execute("PRAGMA table_info(songs)")
    columns = [col[1] for col in c.fetchall()]
    if "capo" not in columns:
        c.execute("ALTER TABLE songs ADD COLUMN capo INTEGER DEFAULT 0")
    if "name" not in columns:
        c.execute("ALTER TABLE songs ADD COLUMN name TEXT")
    if "key" not in columns:
        c.execute("ALTER TABLE songs ADD COLUMN key TEXT DEFAULT ''")
    conn.commit()
    conn.close()

def save_song(name, content, capo, key=""):
    name = name.title()
    # If key is not provided, extract first chord from content
    if not key:
        key = extract_first_chord(content)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name FROM songs where name=?", (name,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return
    c.execute("INSERT INTO songs (name, content, capo, key) VALUES (?, ?, ?, ?)", (name, content, capo, key))
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
    c.execute("SELECT id, name, content, capo, key FROM songs ORDER BY name ASC")
    songs = c.fetchall()
    conn.close()
    return songs

def get_song_by_id(song_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name, content, capo, key FROM songs WHERE id=?", (song_id,))
    song = c.fetchone()
    conn.close()
    if song:
        return song[0], song[1], song[2], song[3]
    return "", "", 0, ""

def update_song_keys():
    """Update all existing songs to have their keys set based on first chord"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, content FROM songs")
    songs = c.fetchall()
    
    for song_id, content in songs:
        if content:
            key = extract_first_chord(content)
            if key:
                c.execute("UPDATE songs SET key=? WHERE id=?", (key, song_id))
    
    conn.commit()
    conn.close()

def update_song(song_id, name, content, capo, key=""):
    """Update an existing song's details"""
    name = name.title()
    # If key is not provided, extract first chord from content
    if not key:
        key = extract_first_chord(content)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE songs SET name=?, content=?, capo=?, key=? WHERE id=?", 
              (name, content, capo, key, song_id))
    conn.commit()
    conn.close()

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
    key = ""
    songs = get_songs()

    # Search query (server-side filtering)
    query = request.args.get("q", "") or ""
    if query:
        qlow = query.lower()
        songs = [s for s in songs if (s[1] and qlow in s[1].lower()) or (s[2] and qlow in s[2].lower())]

    # Get filter parameters from URL
    capo_filter = request.args.get("capo_filter", "")
    key_filter = request.args.get("key_filter", "")

    song_id = request.args.get("song_id")
    if song_id:
        name, input_text, capo, key = get_song_by_id(song_id)

    if request.method == "POST":
        input_text = request.form.get("songtext") or request.form.get("output_text")
        capo = int(request.form.get("capo", 0))
        name = request.form.get("name", "")
        key = request.form.get("key", "")
        action = request.form["action"]

        if action == "up":
            steps = 1
        elif action == "down":
            steps = -1
        elif action == "save":
            save_song(name, request.form.get("output_text") or request.form.get("songtext"), capo, key)
            return redirect(url_for('index'))
        elif action == "edit":
            update_song(song_id, name, request.form.get("output_text") or request.form.get("songtext"), capo, key)
            return redirect(url_for('index', song_id=song_id))
        elif action.startswith("delete_"):
            song_to_delete = int(action.split("_")[1])
            delete_song(song_to_delete)
            return redirect(url_for('index'))
        elif action == "new":
            return redirect(url_for('index'))
        else:
            steps = 0

        output_text = transpose_text(input_text, steps)
        capo = (capo - steps) % 12
        input_text = output_text

    # pass current song id and current query back to template
    return render_template(
        "index.html",
        input_text=input_text,
        output_text=output_text,
        capo=capo,
        name=name,
        key=key,
        songs=songs,
        current_song_id=song_id,
        query=query,
        capo_filter=capo_filter,
        key_filter=key_filter,
    )

if __name__ == "__main__":
    init_db()
    update_song_keys()
    app.run(host="0.0.0.0", debug=True)
