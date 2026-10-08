import os
import math
from flask import Flask, render_template, request, redirect, url_for, jsonify
from pymongo import MongoClient
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB Max upload limit

# ==================== CLOUD ENVIRONMENT CONFIGURATION ====================
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
db = client['sprites_db'] 
sprites_collection = db.spritesrow

CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    print("cloudi...connected")
# =========================================================================

PER_PAGE = 12

@app.route('/')
def index():
    try:
        page = max(1, int(request.args.get('page', 1)))
        total_sprites = sprites_collection.count_documents({})
        total_pages = max(1, math.ceil(total_sprites / PER_PAGE))
        page = min(page, total_pages)
        
        skip_amount = (page - 1) * PER_PAGE
        sprites = list(sprites_collection.find().skip(skip_amount).limit(PER_PAGE))
        
    except Exception as e:
        return f"🚨 Database Connection Error: {str(e)}", 500
        
    return render_template(
        'index.html', 
        sprites=sprites, 
        current_page=page, 
        total_pages=total_pages,
        total_sprites=total_sprites
    )
@app.route('/upload', methods=['POST'])
def upload_sprites():
    category = request.form.get('category', 'general').strip().lower()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    
    if 'sprites' not in request.files:
        return jsonify({"error": "No file field 'sprites' found"}), 400
        
    uploaded_files = request.files.getlist('sprites')
    
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files.filename == ''):
        return jsonify({"error": "No files selected"}), 400

    inserted_count = 0

    # NO MORE TRY/EXCEPT LAYER - LET THE ERROR CRASH LOUDLY TO REVEAL THE BUG
    for file in uploaded_files:
        if file and file.filename != '':
            # 1. Upload file binary payload straight to Cloudinary
            upload_result = cloudinary.uploader.upload(file, folder="sprite_vault")
            image_url = upload_result.get('secure_url')
            
            if not image_url:
                return jsonify({"error": "Cloudinary accepted connection but failed to return an image URL string."}), 500
                
            original_filename = file.filename
            
            # Extract name and strip extension safely without crashing
            name_parts = original_filename.rsplit('.', 1)
            filename_without_extension = name_parts[0]  # Array slice extraction
            clean_name = filename_without_extension.replace('_', ' ').replace('-', ' ').title()
            
            sprite_data = {
                "name": clean_name,
                "filename": original_filename,
                "image_url": image_url, 
                "category": category,
                "tags": tags
            }
            
            # Commit to MongoDB
            sprites_collection.insert_one(sprite_data)
            inserted_count += 1

    return jsonify({"status": "success", "uploaded_count": inserted_count}), 200



# ==================== API ENDPOINTS ====================
@app.route('/api/sprites', methods=['GET'])
def get_all_sprites():
    category = request.args.get('category')
    tag = request.args.get('tag')
    
    query = {}
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
