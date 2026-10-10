import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB Limit

# ==================== CLOUD ENVIRONMENT CONFIGURATION ====================
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/sprites_db')
client = MongoClient(MONGO_URI)
db = client['sprites_db']
sprites_collection = db.spritesrow
print("db connected")

CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    print("cloudi... con...estblsh..")
else:
    cloudinary.config(
        cloud_name = os.environ.get("CLOUD_NAME"),
        api_key = os.environ.get("CLOUD_API_KEY"),
        api_secret = os.environ.get("CLOUD_API_SECRET"),
        secure = True
    )
# =========================================================================

@app.route('/')
def index():
    try:
        raw_sprites = list(sprites_collection.find())
        sprites = []
        for s in raw_sprites:
            s['_id'] = str(s['_id'])  # Format object IDs to strings cleanly
            sprites.append(s)
        return render_template('index.html', sprites=sprites)
    except Exception as e:
        return f"Database Connection/Fetch Failure: {str(e)}", 500

@app.route('/upload', methods=['GET'])
def upload_page():
    """Serves the actual visual web page containing the upload form."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_sprites():
    """Processes the form submission, pushing assets to Cloudinary and metadata to MongoDB."""
    try:
        # Pre-execution environment verification
        if not CLOUDINARY_URL and not os.environ.get("CLOUD_NAME"):
            return "Configuration Error: Cloudinary environmental variables are missing entirely.", 500

        category = request.form.get('category', 'general').strip().lower()
        tags_raw = request.form.get('tags', '')
        tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
        
        # request.files.getlist returns a Python list of file objects
        uploaded_files = request.files.getlist('sprites')
        
        # FIX: Check if the list is empty, or if the first item has an empty filename
        if not uploaded_files or uploaded_files[0].filename == '':
            return "Bad Request: No files were selected for upload.", 400

        for file in uploaded_files:
            # Upload file stream directly to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file,
                folder=f"sprites/{category}"
            )
            
            # Construct document data scheme
            sprite_doc = {
                "filename": file.filename,
                "category": category,
                "tags": tags,
                "cloudinary_url": upload_result.get("secure_url"),
                "public_id": upload_result.get("public_id"),
                "bytes": upload_result.get("bytes"),
                "format": upload_result.get("format")
            }
            
            # Store in MongoDB
            sprites_collection.insert_one(sprite_doc)
            
        return redirect(url_for('index'))

    except Exception as e:
        return f"Upload Processing Failure: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
