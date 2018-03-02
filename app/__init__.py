from flask import Flask, request, jsonify, abort
from pymongo import MongoClient
from bson.objectid import ObjectId

import utils

app = Flask(__name__)

client = MongoClient()

db = client["dtool_info"]
collection = db["datasets"]

app.config["mongo_client"] = client
app.config["mongo_db"] = db
app.config["mongo_collection"] = collection

@app.route("/")
def index():
    message = "{} registered datasets".format(
        app.config["mongo_collection"].count()
    )
    return message


@app.route("/lookup_dataset_info/<uuid>")
def lookup_dataset_info(uuid):
    dataset_info = app.config["mongo_collection"].find_one()
    del dataset_info["_id"]
    return jsonify(dataset_info)


@app.route("/register_dataset", methods=["POST"])
def register_dataset():
    dataset_info = request.get_json()
    uuid = utils.register_dataset(
        app.config["mongo_collection"],
        dataset_info
    )
    if uuid is None:
        abort(400)
    return uuid
