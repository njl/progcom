#!/usr/bin/env python
from flask import Flask, render_template


app = Flask(__name__)

@app.route('/')
def splash():
    return render_template('splash.html')

if __name__ == '__main__':
    app.run(port=4000, debug=True)
