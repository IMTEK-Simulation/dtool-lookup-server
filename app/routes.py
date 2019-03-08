from flask import request, jsonify, abort

from app import app, utils


@app.route("/")
def index():
    message = "{} registered datasets".format(
        app.config["mongo_collection"].count()
    )
    return message


@app.route("/lookup_datasets/<uuid>")
def lookup_datasets(uuid):
    datasets = utils.lookup_datasets(
        app.config["mongo_collection"],
        uuid
    )
    return jsonify(datasets)


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


@app.route("/search_for_datasets", methods=["POST"])
def search_for_datasets():
    query = request.get_json()
    print(query)
    datasets = utils.search_for_datasets(
        app.config["mongo_collection"],
        query
    )
    print("datasets in route {}".format(datasets))
    return jsonify(datasets)
