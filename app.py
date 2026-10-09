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
if db:
    sprites_collection = db.spritesrow

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

@app.route('/upload', methods=['POST'])
def upload_sprites():
    try:
        # Pre-execution environment verification
        if not CLOUDINARY_URL and not os.environ.get("CLOUD_NAME"):
            return "Configuration Error: Cloudinary environmental variables are missing entirely.", 500

        category = request.form.get('category', 'general').strip().lower()
        tags_raw = request.form.get('tags', '')
        tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
        
        uploaded_files = request.files.getlist('sprites')
        
        if not uploaded_files or len(uploaded_files) == 0:
            return "No files selected", 400

        for file in uploaded_files:
            if file and file.filename != '':
                filename = file.filename
                
                # FIXED: Safely isolate the string at index [0] before calling .replace()
                base_name_string = filename.rsplit('.', 1)[0]
                clean_name = base_name_string.replace('_', ' ').replace('-', ' ').title()
                
                # 1. Execute Cloudinary Transmission
                try:
                    upload_result = cloudinary.uploader.upload(
                        file,
                        folder="sprite_vault",
                        transformation=[{"effect": "pixelate"}] 
                    )
                    image_url = upload_result.get('secure_url')
                    
                    if not image_url:
                        raise ValueError("Cloudinary completed upload request but returned a blank secure URL node.")
                        
                except Exception as cloud_err:
                    # STRICT HALT: Stops everything and tells you why Cloudinary failed
                    return f"CRITICAL: Cloudinary Refused Asset Stream. Reason: {str(cloud_err)}", 500
                
                # 2. Execute MongoDB Cluster Save
                try:
                    sprite_data = {
                        "name": clean_name,
                        "filename": filename,
                        "image_url": image_url,
                        "category": category,
                        "tags": tags
                    }
                    sprites_collection.insert_one(sprite_data)
                except Exception as mongo_err:
                    # STRICT HALT: Stops everything and tells you why MongoDB failed
                    return f"CRITICAL: MongoDB Refused Database Insertion. Reason: {str(mongo_err)}", 500

        return redirect(url_for('index'))
        
    except Exception as route_crash:
        return f"Form Transmission Core Failure: {str(route_crash)}", 500

# ==================== REST API ENDPOINTS ====================

@app.route('/api/sprites', methods=['GET'])
def get_all_sprites():
    query = {}
    category = request.args.get('category')
    tag = request.args.get('tag')
    
    if category:
        query['category'] = category.strip().lower()
    if tag:
        query['tags'] = tag.strip().lower()
        
    sprites = list(sprites_collection.find(query))
    output = []
    for s in sprites:
        output.append({
            "id": str(s['_id']),
            "name": s['name'],
            "category": s['category'],
            "tags": s['tags'],
            "image_url": s['image_url']
        })
    return jsonify({"count": len(output), "sprites": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
