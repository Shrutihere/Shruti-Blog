from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, CreateRegistrationForm, LoginForm, Comment
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL',  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES

class Users(UserMixin,db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    posts = relationship('BlogPost', back_populates="author")
    comments = relationship('CommentsTable', back_populates='comment_author')

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    author_id = db.Column(db.Integer, ForeignKey('users.id'))
    author = relationship('Users', back_populates="posts")

    comments = relationship('CommentsTable', back_populates='post')

class CommentsTable( db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text(250), nullable=False)
    author_id = db.Column(db.Integer, ForeignKey('users.id'))

    comment_author = relationship('Users', back_populates="comments")
    post_id = db.Column(db.Integer, ForeignKey('blog_posts.id'))
    post = relationship('BlogPost', back_populates='comments')


db.create_all()

gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)


login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET','POST'])
def get_all_posts():
    print(current_user.get_id())
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=['GET','POST'])
def register():
    form = CreateRegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(request.form['password'], 'pbkdf2:sha256', salt_length=8)
        new_user = Users(
            email=request.form['email'],
            password=hashed_password,
            name=request.form['name']
        )
        if Users.query.filter_by(email=new_user.email).first():
            flash("You have already registered! Log in instead")
            return redirect(url_for('login'))
        else:
            db.session.add(new_user)
            db.session.commit()

        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = Users.query.filter_by(email=email).first()
        if not user:
            flash("You have not registered yet!")
            return redirect(url_for('login'))

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            flash("Incorrect Password! Please try again!")
            return redirect(url_for('login'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET','POST'])
def show_post(post_id):
    form = Comment()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if current_user.get_id():
            new_comment = CommentsTable(
                text=request.form['comment'],
                post_id=post_id,
                author_id=current_user.id
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You are not logged in!")
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, current_user=current_user, form=form)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-post", methods=['GET','POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>")
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
