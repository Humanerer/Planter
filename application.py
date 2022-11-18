from flask import Flask, render_template, redirect, request, make_response, url_for
import boto3
from boto3.dynamodb.conditions import Key

application = app = Flask(__name__)
dbr = boto3.resource('dynamodb', region_name='us-east-1')
dbc = boto3.client("dynamodb", region_name='us-east-1')
s3c = boto3.client("s3", region_name='us-east-1')

#redirects to home page
@app.route('/')
def root():
    return redirect("/home")

#user inputs username and password
@app.route("/signin")
def signIn():
    return render_template('signIn.html')

#user inputs username and password after invalid inputs
@app.route("/signin/invalid")
def signInInvalid():
    return render_template('signIn.html', invalid=True)

#checks if username and password match with database
@app.route("/signin/validate", methods=['GET','POST'])
def signInVal():
    user = request.form.get('username')
    passw = request.form.get('password')

    query = dbc.query(TableName="Users",
        ProjectionExpression="Username, Password",
        KeyConditionExpression='Username = :user AND Password = :pass',
        ExpressionAttributeValues={
            ':user': {'S': user},
            ':pass': {'S': passw}
        })

    if query['Count'] == 1:
        return setCookie(user)

    else:
        return redirect("/signin/invalid")

#registers a new user
@app.route("/register")
def register():
    return render_template('register.html')

#tells user their password
@app.route("/registered/<passw>/<uname>")
def showPassw(passw, uname):
    resp = make_response(render_template("home.html", passw=passw, signed=False))
    resp.set_cookie("uid", uname)
    return resp


#makes sure username is unused
@app.route("/register/validate", methods=['GET','POST'])
def registerVal():
    uname = request.form.get('username')

    query = dbc.query(TableName="Users",
        ProjectionExpression="Username",
        KeyConditionExpression='Username = :user',
        ExpressionAttributeValues={
            ':user': {'S': uname},
        })


    if query['Count'] != 1:
        return redirect("https://vccah09278.execute-api.us-east-1.amazonaws.com/"+uname)

    #pass no match and uname in use
    elif query['Count'] == 1:
        return render_template('register.html', userInUse=True)


#shows all the posts made by users with the highest rating in a timeframe
@app.route("/home")
def home():
    if request.cookies.get("uid") == None:
        return render_template("home.html", signed=False)
    else:
        return render_template("home.html", signed=True)


#shows all posts
@app.route("/allposts")
def allPosts():
    if request.cookies.get("uid") == None:
        signedIn = False
    else:
        signedIn = True

    plants = dbr.Table("Plant")
    plantQuery = plants.scan()
    return render_template("allPosts.html", plants=plantQuery["Items"], signed=signedIn)


#form for posting plants
@app.route("/post")
def post():
    if request.cookies.get("uid") == None:
        return redirect("/home")
    
    else:
        return render_template("post.html")


#uploads if plant name is not already in use
@app.route("/post/validate", methods=['GET','POST'])
def validatePost():
    if request.cookies.get("uid") == None:
        return redirect("/home")
    
    else:
        username = request.cookies.get("uid")
        plantname = request.form.get("plantname")
        plantdesc = request.form.get("plantdesc")
        file = request.files["file"]

        query = dbc.query(TableName="Plant",
            ProjectionExpression="Username, Plantname",
            KeyConditionExpression="Username = :user AND Plantname = :pname",
            ExpressionAttributeValues={
                ':user': {'S': username},
                ':pname' : {'S': plantname}
            })

        if (query["Count"] == 1):
            return redirect("/post/invalid")
        
        else:
            plants = dbr.Table('Plant')
            plants.put_item(
                Item={
                    "Username" : username,
                    "Plantname" : plantname,
                    "Desc" : plantdesc,
                    "Imagename" : file.filename
                }
            )
            if file.filename != '':
                s3c.upload_fileobj(file, "3849758-plant-bucket", username+file.filename,
                ExtraArgs={"ACL": "public-read"})
            return redirect("/myplants")


#if postname is already used by user
@app.route("/post/invalid")
def invalidPost():
    if request.cookies.get("uid") == None:
        return redirect("/home")
    
    else:
        return render_template("post.html", pname=True)


#shows the users plants if theyre logged in
@app.route("/myplants")
def myPlants():
    if request.cookies.get("uid") == None:
        return redirect("/home")
    else:
        username = request.cookies.get("uid")
        user = dbr.Table("Users")
        userQuery = user.query(
            KeyConditionExpression=Key('Username').eq(username)
        )
        plants = dbr.Table("Plant")
        plantQuery = plants.query(
            KeyConditionExpression=Key('Username').eq(username)
        )
        return render_template('myProfile.html', joinDate=userQuery["Items"], plants=plantQuery["Items"], signed=True)


#deletes plant
@app.route("/myplants/delete/<plantname>")
def deletePlant(plantname):
    if request.cookies.get("uid") == None:
        return redirect("/home")

    username = request.cookies.get("uid")
    plants = dbr.Table("Plant")
    plants.delete_item(
        Key={
            'Username': username,
            'Plantname': plantname
        }
    )
    return redirect("/myplants")


#finds posts with matching details
@app.route("/searchposts", methods=['GET','POST'])
def posts():
    searchKey = request.form.get("searchKey")
    return redirect("/searchPosts/"+searchKey)


#finds posts with matching details
@app.route("/searchPosts/<searchKey>")
def searchPosts(searchKey):
    if request.cookies.get("uid") != None:
        signed=True
    
    else:
        signed=False
    
    plants = dbr.Table("Plant")
    plantQuery = plants.scan()
    
    plantList = []
    for item in plantQuery["Items"]:
        if item["Plantname"].lower().find(searchKey.lower()) != -1 or item["Desc"].lower().find(searchKey.lower()) != -1:
            plantList.append(item)
    return render_template("searchposts.html", signed=signed, plants=plantList)


#shows user's posts, username, and profile description
#maybe friend groups/communities too
@app.route('/profile/<username>')
def profile(username):
    if request.cookies.get("uid") == None:
        signed = False
    else:
        signed = True

    user = dbr.Table("Users")
    userQuery = user.query(
        KeyConditionExpression=Key('Username').eq(username)
    )

    if userQuery['Count'] != 1:
        return render_template('profile.html', signed=signed, notExists = True)

    else:
        plants = dbr.Table("Plant")
        plantQuery = plants.query(
            KeyConditionExpression=Key('Username').eq(username)
        )

        if plantQuery["Count"] == 0:
            return render_template("profile.html", plants=plantQuery["Items"], signed=signed, noPosts=True)

        else:
            return render_template("profile.html", plants=plantQuery["Items"], signed=signed, thisUser=userQuery["Items"])


#sets cookie and redirects to home
@app.route("/loggedin")
def setCookie(username):
    resp = make_response(redirect("/home"))
    resp.set_cookie("uid", username)
    return resp


#remove cookie and return to home
@app.route("/logout")
def logout():
    resp = make_response(redirect("/home"))
    resp.set_cookie("uid", "", expires=0)
    return resp

#used for easier debugging on localhost
if __name__ == '__main__':
   app.run(debug=True)