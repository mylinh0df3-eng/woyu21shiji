# ==================== 导入模块 / Import Modules ====================
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
import json
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps

# ==================== 初始化Flask应用 / Initialize Flask App ====================
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # 密钥，用于session加密 / Secret key for session
app.config['UPLOAD_FOLDER'] = 'uploads'  # 上传文件夹 / Upload folder
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大上传16MB / Max upload 16MB

# ==================== 创建必要文件夹 / Create Required Folders ====================
os.makedirs('data', exist_ok=True)  # 数据文件夹 / Data folder
os.makedirs('uploads', exist_ok=True)  # 上传文件夹 / Upload folder

# ==================== 数据库操作函数 / Database Functions ====================
def load_data(filename):
    """加载JSON数据文件 / Load JSON data file"""
    path = os.path.join('data', filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(filename, data):
    """保存JSON数据文件 / Save JSON data file"""
    path = os.path.join('data', filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== 初始化数据 / Initialize Data ====================
def init_data():
    """首次运行时初始化数据 / Initialize data on first run"""
    # 初始化用户表 / Initialize users table
    if not os.path.exists('data/users.json'):
        # 创建管理员账号 / Create admin account
        admin = {
            "id": "admin001",
            "username": "admin",  # 管理员用户名 / Admin username
            "password": "admin123",  # 管理员密码（部署后请修改）/ Admin password (change after deploy)
            "email": "admin@photo.com",
            "avatar": "",
            "bio": "管理员 / Administrator",
            "role": "admin",  # 角色：admin=管理员 / Role: admin
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_data('users.json', [admin])
    
    # 初始化图片表 / Initialize images table
    if not os.path.exists('data/images.json'):
        save_data('images.json', [])
    
    # 初始化点赞表 / Initialize likes table
    if not os.path.exists('data/likes.json'):
        save_data('likes.json', [])
    
    # 初始化评论表 / Initialize comments table
    if not os.path.exists('data/comments.json'):
        save_data('comments.json', [])
    
    # 初始化收藏表 / Initialize favorites table
    if not os.path.exists('data/favorites.json'):
        save_data('favorites.json', [])

init_data()

# ==================== 辅助函数 / Helper Functions ====================
def get_current_user():
    """获取当前登录用户 / Get current logged-in user"""
    user_id = session.get('user_id')
    if user_id:
        users = load_data('users.json')
        return next((u for u in users if u['id'] == user_id), None)
    return None

def is_admin():
    """检查当前用户是否是管理员 / Check if current user is admin"""
    user = get_current_user()
    return user and user.get('role') == 'admin'

def login_required(f):
    """登录验证装饰器 / Login required decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 页面路由 / Page Routes ====================

@app.route('/')
def index():
    """首页 - 瀑布流展示公开图片 / Homepage - Show public images"""
    user = get_current_user()
    images = load_data('images.json')
    users = load_data('users.json')
    likes = load_data('likes.json')
    comments = load_data('comments.json')
    
    # 只显示公开的图片 / Only show public images
    public_images = [img for img in images if img.get('is_public', False)]
    
    # 为每张图片添加用户信息和统计 / Add user info and stats for each image
    for img in public_images:
        img['user'] = next((u for u in users if u['id'] == img['user_id']), None)
        img['like_count'] = len([l for l in likes if l['image_id'] == img['id']])
        img['comment_count'] = len([c for c in comments if c['image_id'] == img['id']])
    
    # 按时间倒序排列 / Sort by newest first
    public_images.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('index.html', images=public_images, user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录/注册页面 / Login/Register page"""
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_data('users.json')
        
        if action == 'login':
            # 登录处理 / Login process
            user = next((u for u in users if u['username'] == username and u['password'] == password), None)
            if user:
                session['user_id'] = user['id']
                return jsonify({"success": True, "message": "登录成功 / Login successful"})
            return jsonify({"success": False, "message": "用户名或密码错误 / Wrong username or password"})
        
        elif action == 'register':
            # 注册处理 / Register process
            if any(u['username'] == username for u in users):
                return jsonify({"success": False, "message": "用户名已存在 / Username already exists"})
            
            new_user = {
                "id": str(uuid.uuid4())[:12],
                "username": username,
                "password": password,
                "email": request.form.get('email', ''),
                "avatar": "",
                "bio": "",
                "role": "user",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            users.append(new_user)
            save_data('users.json', users)
            session['user_id'] = new_user['id']
            return jsonify({"success": True, "message": "注册成功 / Registration successful"})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录 / Logout"""
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/detail/<image_id>')
def detail(image_id):
    """图片详情页 / Image detail page"""
    user = get_current_user()
    images = load_data('images.json')
    users = load_data('users.json')
    likes = load_data('likes.json')
    comments = load_data('comments.json')
    
    image = next((img for img in images if img['id'] == image_id), None)
    if not image:
        return "图片不存在 / Image not found", 404
    
    # 检查权限：私密图片只有上传者和管理员能看 / Check permission
    if not image.get('is_public', False):
        if not user or (user['id'] != image['user_id'] and user.get('role') != 'admin'):
            return "无权限查看 / No permission", 403
    
    # 获取图片发布者信息 / Get uploader info
    image['user'] = next((u for u in users if u['id'] == image['user_id']), None)
    
    # 点赞统计 / Like stats
    image['like_count'] = len([l for l in likes if l['image_id'] == image_id])
    image['is_liked'] = any(l['user_id'] == user['id'] and l['image_id'] == image_id for l in likes) if user else False
    
    # 是否已收藏 / Is favorited
    favorites = load_data('favorites.json')
    image['is_favorited'] = any(f['user_id'] == user['id'] and f['image_id'] == image_id for f in favorites) if user else False
    
    # 获取评论 / Get comments
    image_comments = [c for c in comments if c['image_id'] == image_id]
    for c in image_comments:
        c['user'] = next((u for u in users if u['id'] == c['user_id']), None)
    image_comments.sort(key=lambda x: x['created_at'], reverse=True)
    
    # 相关推荐（同用户的其他公开图片）/ Related images
    related = [img for img in images if img['user_id'] == image['user_id'] and img['id'] != image_id and img.get('is_public', False)][:4]
    
    return render_template('detail.html', image=image, comments=image_comments, related=related, user=user)

@app.route('/profile/<user_id>')
def profile(user_id):
    """个人主页 / Profile page"""
    current_user = get_current_user()
    users = load_data('users.json')
    profile_user = next((u for u in users if u['id'] == user_id), None)
    
    if not profile_user:
        return "用户不存在 / User not found", 404
    
    images = load_data('images.json')
    likes = load_data('likes.json')
    comments = load_data('comments.json')
    
    # 获取该用户的图片 / Get this user's images
    user_images = [img for img in images if img['user_id'] == user_id]
    
    # 如果是当前用户自己，显示所有图片 / If viewing own profile, show all
    # 如果是别人，只显示公开图片 / If viewing others, only show public
    if not current_user or current_user['id'] != user_id:
        user_images = [img for img in user_images if img.get('is_public', False)]
    
    for img in user_images:
        img['like_count'] = len([l for l in likes if l['image_id'] == img['id']])
        img['comment_count'] = len([c for c in comments if c['image_id'] == img['id']])
    
    user_images.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('profile.html', profile_user=profile_user, images=user_images, current_user=current_user)

@app.route('/admin')
@login_required
def admin():
    """管理后台 - 仅管理员可访问 / Admin panel - only for admin"""
    if not is_admin():
        return "无权限 / No permission", 403
    
    users = load_data('users.json')
    images = load_data('images.json')
    
    # 为每张图片添加用户名 / Add username to each image
    for img in images:
        img['username'] = next((u['username'] for u in users if u['id'] == img['user_id']), '未知')
    
    images.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('admin.html', images=images, users=users)

# ==================== API接口 / API Routes ====================

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    """上传图片 / Upload image"""
    try:
        user = get_current_user()
        title = request.form.get('title', '无标题 / No title')
        
        # 处理上传的图片 / Process uploaded image
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                filename = str(uuid.uuid4())[:8] + '_' + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = '/uploads/' + filename
            else:
                return jsonify({"success": False, "message": "请选择图片 / Please select an image"})
        else:
            return jsonify({"success": False, "message": "请选择图片 / Please select an image"})
        
        images = load_data('images.json')
        new_image = {
            "id": str(uuid.uuid4())[:12],
            "title": title,
            "image_url": image_url,
            "user_id": user['id'],
            "is_public": False,  # 默认私密，等管理员审核 / Default private, wait for admin review
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        images.append(new_image)
        save_data('images.json', images)
        
        return jsonify({"success": True, "message": "上传成功，等待审核 / Upload successful, pending review"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/api/delete_image', methods=['POST'])
@login_required
def api_delete_image():
    """删除图片 / Delete image"""
    user = get_current_user()
    data = request.get_json()
    image_id = data.get('image_id')
    
    images = load_data('images.json')
    image = next((img for img in images if img['id'] == image_id), None)
    
    if not image:
        return jsonify({"success": False, "message": "图片不存在 / Image not found"})
    
    # 只有上传者和管理员能删除 / Only uploader and admin can delete
    if user['id'] != image['user_id'] and user.get('role') != 'admin':
        return jsonify({"success": False, "message": "无权限 / No permission"})
    
    images = [img for img in images if img['id'] != image_id]
    save_data('images.json', images)
    
    return jsonify({"success": True, "message": "删除成功 / Deleted successfully"})

@app.route('/api/toggle_public', methods=['POST'])
@login_required
def api_toggle_public():
    """切换图片公开/私密（仅管理员）/ Toggle public/private (admin only)"""
    if not is_admin():
        return jsonify({"success": False, "message": "仅管理员可操作 / Admin only"})
    
    data = request.get_json()
    image_id = data.get('image_id')
    
    images = load_data('images.json')
    for img in images:
        if img['id'] == image_id:
            img['is_public'] = not img.get('is_public', False)
            status = "公开 / Public" if img['is_public'] else "私密 / Private"
            save_data('images.json', images)
            return jsonify({"success": True, "message": f"已设为{status} / Set to {status}", "is_public": img['is_public']})
    
    return jsonify({"success": False, "message": "图片不存在 / Image not found"})

@app.route('/api/like', methods=['POST'])
@login_required
def api_like():
    """点赞/取消点赞 / Like/Unlike"""
    user = get_current_user()
    data = request.get_json()
    image_id = data.get('image_id')
    
    likes = load_data('likes.json')
    
    # 检查是否已点赞 / Check if already liked
    existing = next((l for l in likes if l['user_id'] == user['id'] and l['image_id'] == image_id), None)
    
    if existing:
        # 取消点赞 / Unlike
        likes = [l for l in likes if not (l['user_id'] == user['id'] and l['image_id'] == image_id)]
        save_data('likes.json', likes)
        return jsonify({"success": True, "liked": False, "message": "已取消点赞 / Unliked"})
    else:
        # 点赞 / Like
        likes.append({
            "id": str(uuid.uuid4())[:12],
            "user_id": user['id'],
            "image_id": image_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data('likes.json', likes)
        return jsonify({"success": True, "liked": True, "message": "点赞成功 / Liked"})

@app.route('/api/favorite', methods=['POST'])
@login_required
def api_favorite():
    """收藏/取消收藏 / Favorite/Unfavorite"""
    user = get_current_user()
    data = request.get_json()
    image_id = data.get('image_id')
    
    favorites = load_data('favorites.json')
    
    existing = next((f for f in favorites if f['user_id'] == user['id'] and f['image_id'] == image_id), None)
    
    if existing:
        favorites = [f for f in favorites if not (f['user_id'] == user['id'] and f['image_id'] == image_id)]
        save_data('favorites.json', favorites)
        return jsonify({"success": True, "favorited": False, "message": "已取消收藏 / Unfavorited"})
    else:
        favorites.append({
            "id": str(uuid.uuid4())[:12],
            "user_id": user['id'],
            "image_id": image_id,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data('favorites.json', favorites)
        return jsonify({"success": True, "favorited": True, "message": "收藏成功 / Favorited"})

@app.route('/api/comment', methods=['POST'])
@login_required
def api_comment():
    """发表评论/回复 / Post comment/reply"""
    user = get_current_user()
    data = request.get_json()
    image_id = data.get('image_id')
    content = data.get('content', '')
    parent_id = data.get('parent_id', None)  # 回复的评论ID / Reply to comment ID
    
    if not content.strip():
        return jsonify({"success": False, "message": "请输入评论内容 / Please enter comment"})
    
    comments = load_data('comments.json')
    new_comment = {
        "id": str(uuid.uuid4())[:12],
        "user_id": user['id'],
        "image_id": image_id,
        "content": content,
        "parent_id": parent_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    comments.append(new_comment)
    save_data('comments.json', comments)
    
    return jsonify({"success": True, "message": "评论成功 / Comment posted"})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """访问上传的文件 / Access uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== 启动应用 / Run App ====================
if __name__ == '__main__':
    print("=" * 50)
    print("  照片社区系统已启动！/ Photo Community Started!")
    print("  管理员账号 / Admin: admin / admin123")
    print("  访问地址 / URL: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
