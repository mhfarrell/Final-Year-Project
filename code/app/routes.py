import os
from threading import Lock
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from app import app
import time
import bcrypt
import sys, getopt, pprint
import pymongo
from pymongo import MongoClient
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect

async_mode = None
c = MongoClient('mongodb://admin:Admin123@ds145555.mlab.com:45555/chatdatabase')
db= c.chatdatabase
#make this a hashed version of something unique to the user
app.secret_key = 'shush_its_secret'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock()

def loadChat():
    myQuery = { '$or': [ { 'recipient': session['username'] }, { 'sender': session['username'] } ] }
    cursor = db.chat.distinct('chatID', myQuery)
    
    chats = []
    for doc in cursor:
        cursor2 = db.chat.find({"chatID" : doc}, limit = 1).sort([('msgID',  pymongo.DESCENDING)])
        chats.append(cursor2)
    return chats


def loadContact(search):
    print('search text is: ' + search)
    myQuery = {'username' : {'$ne' : session['username']},
           '$and' : [{'$or' : [
                 {'username' : {'$regex' : search, '$options': 'i'}},
                 {'surname' : {'$regex' : search, '$options': 'i'}},
                 {'firstName' : {'$regex' : search, '$options': 'i'}},
                 {'email' : {'$regex' : search, '$options': 'i'}},
                 {'company' : {'$regex' : search, '$options': 'i'}}]}]}
    cursor = db.users.find(myQuery)
    payload = []
    content = {}
    for doc in cursor:
        print('username is: ' + doc['username'])
        content = {'username' : doc['username']}
        payload.append(content)
        
    return payload


@socketio.on('connect', namespace='/test')
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)
    emit('my_response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)

def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        socketio.emit('my_response',
                      {'data': 'Server generated event', 'count': count},
                      namespace='/test')

@app.route('/')
@app.route('/index')
def index():
    if 'username' in session:
        return render_template('index.html',\
                               current_user=session['username'],\
                               chats=loadChat())

    return render_template('login.html', \
                           Form='login-form', \
                           altForm='register-form')

@app.route('/search', methods=['POST', 'GET'])
def search():
    name = request.form['name']
    search = request.form['search']
    if name and search:
        return jsonify(loadContact(search))
      
    return jsonify({'error' : 'Missing data!'})

@app.route('/login', methods=['POST'])
def login():
    users = db.users
    loginUser = users.find_one({'username' : request.form['username']})
    if loginUser:
        hashPass = bcrypt.hashpw(request.form['password'].encode('utf-8'), loginUser['password'])
        if loginUser:
            if hashPass == loginUser['password']:
                session['username'] = request.form['username']
                return render_template('index.html',\
                                       current_user=session['username'],\
                                       chats=loadChat())

    return render_template('login.html', \
                           Form='login-form', \
                           altForm='register-form', \
                           loginMessage='Invalid Password/Username')

@app.route('/logout')
def logout():
    session.pop('username')
    return render_template('login.html', \
                           Form='login-form', \
                           altForm='register-form', \
                           loginMessage='You have been logged out!')

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        users = db.users
        #userCheck is checking database if the username from the new user exists already
        userCheck = users.find_one({'username' : request.form['username']})
        #If the username is unclaimed the new user can register
        if userCheck is None:
            hashPass = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
            users.insert({'username' : request.form['username'], 'password' : hashPass, 'firstName' : request.form['firstname'], 'surname' : request.form['surname'], 'email' : request.form['email'], 'company' : request.form['company']})
            session['username'] = request.form['username']
            return render_template('index.html',\
                                   current_user=session['username'],\
                                   chats=loadChat())
        
    return render_template('login.html', \
                           altForm='login-form', \
                           Form='register-form', \
                           registerMessage='Sorry that username already exists')



#Socket.io

@socketio.on('join', namespace='/test')
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'Joined Room: ' + ', '.join(rooms()),
          'count': session['receive_count']})
    myQuery = {'chatID' : message['room']}
    cursor = db.chat.find(myQuery) 
    for doc in cursor:
        emit('my_response',
             {'data': doc['data'], 'username': doc['sender'], 'datetime':doc['datetime'],'count': session['receive_count']},
             room=message['room'])

@socketio.on('leave', namespace='/test')
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'Left Room: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('sendMessage', namespace='/test')
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'testing message: ' + ', ' + message['data'],
          'count': session['receive_count']})
    newID = "msg" + str(db.chat.count()+1)
    myDict = {"msgID": newID , "chatID" : message['room'], "recipient" : message['recipient'], "sender": message['sender'], "datetime": int(time.time()) , "data": message['data']}    
    db.chat.insert_one(myDict)
    emit('my_response',
         {'data': message['data'], 'username': message['sender'], 'count': session['receive_count']},
         room=message['room'])


@socketio.on('disconnect_request', namespace='/test')
def disconnect_request():
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'Disconnected!', 'count': session['receive_count']})
    disconnect()


