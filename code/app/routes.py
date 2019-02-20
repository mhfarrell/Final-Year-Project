import os
from flask import Flask, render_template, request, redirect, url_for, session
from app import app
import bcrypt
import sys, getopt, pprint
from pymongo import MongoClient

c = MongoClient('mongodb://admin:Admin123@ds119024.mlab.com:19024/chatdatabase')
db= c.chatdatabase

@app.route('/')
@app.route('/index')
def index():
    if 'username' in session:
        return render_template('index.html')
    
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    users = db.users
    loginUser = users.find_one({'username' : request.form['username']})
    hashPass = bcrypt.hashpw(request.form['password'].encode('utf-8'), loginUser['password'])
    if loginUser:
        if hashPass == loginUser['password']:
            session['username'] = request.form['username']
            return render_template('index.html')
    return render_template('login.html', loginMessage='Invalid Password/Username')

@app.route('/logout')
def logout():
    session['username'] = ''
    return render_template('login.html', loginMessage='You have been logged out!')

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        users = db.users
        #userCheck is checking database if the username from the new user exists already
        userCheck = users.find_one({'username' : request.form['username']})
        #If the username is unclaimed the new user can register
        if userCheck is None:
            hashPass = bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt())
            users.insert({'username' : request.form['username'], 'password' : hashpass})
            session['username'] = request.form['username']
            return render_template('index.html')
        
    return render_template('login.html', loginMessage='Sorry that username already exists')
