from flask import Flask, jsonify, flash, send_from_directory, render_template, request, make_response, redirect
from mongita import MongitaClientDisk
from bson import ObjectId

import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

# create a mongita client connection
client = MongitaClientDisk()

# open the quotes database
quotes_db = client.quotes_db
session_db = client.session_db
user_db = client.user_db

import uuid
import passwords
import secrets

app.secret_key = secrets.token_hex(32)

@app.route("/", methods=["GET"])
@app.route("/quotes", methods=["GET"])
def get_quotes():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        response = redirect("/logout")
        return response
    assert len(session_data) == 1
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    # open the quotes collection
    quotes_collection = quotes_db.quotes_collection
    # load the data
    data = list(quotes_collection.find({"owner": user}))
    for item in data:
        item["_id"] = str(item["_id"])
        item["object"] = ObjectId(item["_id"])
        # Fetch comments for each quote
        item["comments"] = []
        if "comments" in item:
            item["comments"] = item["comments"]
    # display the data
    html = render_template(
        "quotes.html",
        data=data,
        user=user,
    )
    response = make_response(html)
    response.set_cookie("session_id", session_id)
    return response


@app.route("/login", methods=["GET"])
def get_login():
    #userCollection = user_db.user_collection
    #usersList = list(userCollection.find({}))
    #print(usersList)
    session_id = request.cookies.get("session_id", None)
    print("Pre-login session id = ", session_id)
    if session_id:
        return redirect("/quotes")
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def post_login():
    username = request.form["username"]
    password = request.form["password"]

    # open the user collection
    user_collection = user_db.user_collection

    app.logger.info("All entries in the user collection:")
    for entry in user_collection.find():
        app.logger.info(entry)

    # look for the user
    count = user_collection.count_documents({"user": username})
    user_data = user_collection.find_one({"user": username})
    if count == 0:
        flash("Incorrect username or password")
        response = redirect("/login")
        response.delete_cookie("session_id")
        return response
    storedPass = user_data.get("pass", "")
    storedSalt = user_data.get("salt", "")
    if passwords.check_password(password, storedPass, storedSalt):
        session_id = str(uuid.uuid4())
        # open the session collection
        session_collection = session_db.session_collection
        # insert the user
        session_collection.delete_one({"session_id": session_id})
        session_data = {"session_id": session_id, "user": username}
        session_collection.insert_one(session_data)
        response = redirect("/quotes")
        response.set_cookie("session_id", session_id)
        return response
    else:
        flash("Incorrect username or password")
        response = redirect("/login")
        response.delete_cookie("session_id")
        return response

@app.route("/register", methods=["GET"])
def get_register():
   return render_template("register.html") 


@app.route("/register", methods=["POST"])
def post_register():
    userCollection = user_db.user_collection
    newUsername = request.form["username"]
    newPassword = request.form["password"]
    userData = list(userCollection.find({"user": newUsername}))
    if len(userData) > 0:
        flash("Username is not unique, please try again.")
        response = redirect("/register")
        return response
    hashed_password, salt = passwords.hash_password(newPassword)
    newUserEntry = {"user": newUsername, "pass": hashed_password, "salt": salt}
    userCollection.insert_one(newUserEntry)
    response = redirect("/login")
    return response


@app.route("/logout", methods=["GET"])
def get_logout():
    # get the session id
    session_id = request.cookies.get("session_id", None)
    if session_id:
        # open the session collection
        session_collection = session_db.session_collection
        # delete the session
        session_collection.delete_one({"session_id": session_id})
    response = redirect("/login")
    response.delete_cookie("session_id")
    return response


@app.route("/add", methods=["GET"])
def get_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    return render_template("add_quote.html")


@app.route("/add", methods=["POST"])
def post_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        response = redirect("/logout")
        return response
    assert len(session_data) == 1
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    text = request.form.get("text", "")
    author = request.form.get("author", "")
    allow_comment = request.form.get("allow_comments", False) == "true"
    public = request.form.get("public", "") == "on"
    if text != "" and author != "":
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # insert the quote
        quote_data = {"owner": user, "text": text, "author": author, "public": public ,"allow_comment": allow_comment}
        quotes_collection.insert_one(quote_data)
    # usually do a redirect('....')

    app.logger.info("All quotes in the quotes collection:")
    for entry in quotes_collection.find():
        app.logger.info(entry)

    return redirect("/quotes")


@app.route("/edit/<id>", methods=["GET"])
def get_edit(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # get the item
        data = quotes_collection.find_one({"_id": ObjectId(id)})
        data["id"] = str(data["_id"])
        return render_template("edit_quote.html", data=data)
    # return to the quotes page
    return redirect("/quotes")


@app.route("/edit", methods=["POST"])
def post_edit():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    _id = request.form.get("_id", None)
    text = request.form.get("text", "")
    author = request.form.get("author", "")
    public = request.form.get("public", "") == "on"
    if _id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # update the values in this particular record
        values = {"$set": {"text": text, "author": author, "public": public}}
        data = quotes_collection.update_one({"_id": ObjectId(_id)}, values)
    # do a redirect('....')
    return redirect("/quotes")


@app.route("/delete", methods=["GET"])
@app.route("/delete/<id>", methods=["GET"])
def get_delete(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # delete the item
        quotes_collection.delete_one({"_id": ObjectId(id)})
    # return to the quotes page
    return redirect("/quotes")

@app.route("/api/quotes", methods=["GET"])
def api_quotes():
    quotes = []
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return jsonify(quotes)
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        return jsonify(quotes)
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    # open the quotes collection
    quotes_collection = quotes_db.quotes_collection
    # load the data
    data = list(quotes_collection.find({"owner":user}))
    publicData = list(quotes_collection.find({"public": True, "owner":{"$ne": user}}))
    for item in data:
        item["_id"] = str(item["_id"])
    for item in publicData:
        item["_id"] = str(item["_id"])
    return jsonify({
        'quotes': data,
        'publicQuotes': publicData,
        'user': user
    })

@app.route("/add_comment/<id>", methods=["GET"])
def get_add_comment(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # Open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # Get the quote item
        quote = quotes_collection.find_one({"_id": ObjectId(id)})
        if quote:
            app.logger.info("Quote entry: %s", quote)
            # Check if comments are allowed for this quote
            if not quote.get("allow_comment", True):
                app.logger.info("Comments not allowed for quote: %s", id)
                return redirect("/quotes")
            # Render the add_comment.html template with the quote data
            return render_template("add_comment.html", quote=quote)
    # Redirect to the quotes page if the quote ID is not found or if there's no session ID
    return redirect("/quotes")

@app.route("/add_comment/<id>", methods=["POST"])
def post_add_comment(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return redirect("/login")
    
    if id:
        # Get the comment text from the form
        comment_text = request.form.get("commentText", "")
        if not comment_text:
            return redirect(f"/add_comment/{id}")
        
        # Open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # Get the quote item
        quote = quotes_collection.find_one({"_id": ObjectId(id)})
        if quote:
            if "comments" not in quote:
                quote["comments"] = []
            # Generate a unique ID for the comment
            comment_id = str(uuid.uuid4())
            # Add the comment to the quote
            quote["comments"].append({"_id": comment_id, "text": comment_text})
            # Update the quote in the database
            quotes_collection.update_one({"_id": ObjectId(id)}, {"$set": {"comments": quote["comments"]}})
            app.logger.info("Quote entry after adding comment:")
            app.logger.info(quote)
            return redirect("/quotes")
    
    # Redirect to the quotes page if the quote ID is not found or if there's no session ID
    return redirect("/quotes")

@app.route("/delete_comment/<quote_id>/<comment_id>", methods=["GET"])
def post_delete_comment(quote_id=None, comment_id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return redirect("/login")

    if quote_id and comment_id:
        # Open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # Get the quote item
        quote = quotes_collection.find_one({"_id": ObjectId(quote_id)})
        if quote and "comments" in quote:
            # Find the comment in the comments list
            comment_index = None
            for index, comment in enumerate(quote["comments"]):
                if comment.get("_id") == comment_id:
                    comment_index = index
                    break
            
            # If the comment is found, remove it from the list
            if comment_index is not None:
                del quote["comments"][comment_index]
                # Update the quote in the database
                quotes_collection.update_one({"_id": ObjectId(quote_id)}, {"$set": {"comments": quote["comments"]}})
                app.logger.info("Quote entry after deleting comment:")
                app.logger.info(quote)
                return redirect("/quotes")
    
    # Redirect to the quotes page if the quote ID or comment ID is not found
    return redirect("/quotes")
