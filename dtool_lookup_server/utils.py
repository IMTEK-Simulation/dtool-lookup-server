"""Utility functions."""

from sqlalchemy.sql import exists

from dtool_lookup_server import (
    mongo,
    sql_db,
    AuthenticationError,
    ValidationError,
    MONGO_COLLECTION,
)
from dtool_lookup_server.sql_models import (
    User,
    BaseURI,
    Dataset,
)

DATASET_INFO_REQUIRED_KEYS = (
    "uuid",
    "base_uri",
    "uri",
    "name",
    "type",
    "readme",
)


#############################################################################
# Private helper functions.
#############################################################################

def _get_user_obj(username):
    return User.query.filter_by(username=username).first()


def _get_base_uri_obj(base_uri):
    return BaseURI.query.filter_by(base_uri=base_uri).first()


#############################################################################
# User helper functions
#############################################################################

def user_exists(username):
    if _get_user_obj(username) is None:
        return False
    return True


def get_user_obj(username):
    user = _get_user_obj(username)
    if user is None:
        raise(AuthenticationError())
    return user


def register_users(users):
    """Register a list of users in the system.

    Example input structure::

        [
            {"username": "magic.mirror", "is_admin": True},
            {"username": "snow.white", "is_admin": False},
            {"username": "dopey"},
            {"username": "sleepy"},
        ]

    If a user is already registered in the system it is skipped. To change the
    ``is_admin`` status of an existing user use the
    :func:`dtool_lookup_server.utils.set_user_is_admin`` function.
    """

    for user in users:
        username = user["username"]
        is_admin = user.get("is_admin", False)

        # Skip existing users.
        if sql_db.session.query(
            exists().where(User.username == username)
        ).scalar():
            continue

        user = User(username=username, is_admin=is_admin)
        sql_db.session.add(user)

    sql_db.session.commit()


def list_users():
    """Return list of users."""
    users = []
    for u in User.query.all():
        users.append(u.as_dict())
    return users


def get_user_info(username):
    """Return information about a user as a dictionary.

    Return None if the user does not exist.
    """
    user = User.query.filter_by(username=username).first()

    if user is None:
        return None

    return user.as_dict()


#############################################################################
# Dataset list/search/lookup helper functions.
#############################################################################

def list_datasets_by_user(username):
    """List the datasets the user has access to.

    Returns list of dicts if user is valid and has access to datasets.
    Returns empty list if user is valid but has not got access to any datasets.
    Raises AuthenticationError if user is invalid.
    """
    user = get_user_obj(username)

    datasets = []
    for base_uri in user.search_base_uris:
        for ds in base_uri.datasets:
            datasets.append(ds.as_dict())
    return datasets


def search_datasets_by_user(username, query):
    """Search the datasets the user has access to.

    Returns list of dicts if user is valid and has access to datasets.
    Returns empty list if user is valid but has not got access to any datasets.
    Returns None if user is invalid.
    """
    user = get_user_obj(username)

    datasets = []
    for base_uri in user.search_base_uris:
        base_uri_query = query.copy()
        base_uri_query["base_uri"] = base_uri.base_uri
        cx = mongo.db[MONGO_COLLECTION].find(base_uri_query, {"_id": False})
        for ds in cx:
            datasets.append(ds)

    return datasets


def lookup_datasets_by_user_and_uuid(username, uuid):
    """Return list of dataset with matching uuid.

    Returns list of dicts if user is valid and has access to datasets.
    Returns empty list if user is valid but has not got access to any datasets.
    Returns AuthenticationError if user is invalid.
    """
    user = get_user_obj(username)

    datasets = []
    query = sql_db.session.query(Dataset, BaseURI, User)  \
        .filter(Dataset.uuid == uuid)  \
        .filter(User.username == username)  \
        .filter(BaseURI.id == Dataset.base_uri_id)  \
        .filter(User.search_base_uris.any(BaseURI.id == Dataset.base_uri_id)) \
        .all()
    for ds, base_uri, user in query:
        datasets.append(ds.as_dict())

    return datasets


#############################################################################
# Base URI helper functions
#############################################################################

def base_uri_exists(base_uri):
    """Return True if the base URI has been registered."""
    if _get_base_uri_obj(base_uri) is None:
        return False
    return True


def get_base_uri_obj(base_uri):
    """Return SQLAlchemy BaseURI object."""
    base_uri_obj = _get_base_uri_obj(base_uri)
    if base_uri_obj is None:
        raise(ValidationError(
            "Base URI {} not registered".format(base_uri)
        ))
    return base_uri_obj


def register_base_uri(base_uri):
    """Register a base URI in the dtool lookup server."""
    base_uri = BaseURI(base_uri=base_uri)
    sql_db.session.add(base_uri)
    sql_db.session.commit()


def list_base_uris():
    """List the base URIs in the dtool lookup server."""
    base_uris = []
    for bu in BaseURI.query.all():
        base_uris.append(bu.as_dict())
    return base_uris


#############################################################################
# Permission helper functions
#############################################################################

def show_permissions(base_uri_str):
    """Return the permissions of on a base URI as a dictionary."""
    base_uri = get_base_uri_obj(base_uri_str)
    return base_uri.as_dict()


def update_permissions(permissions):
    """Rewrite permissions."""
    base_uri = get_base_uri_obj(permissions["base_uri"])
    for username in permissions["users_with_search_permissions"]:
        if user_exists(username):
            user = get_user_obj(username)
            user.search_base_uris.append(base_uri)
    for username in permissions["users_with_register_permissions"]:
        if user_exists(username):
            user = get_user_obj(username)
            user.register_base_uris.append(base_uri)
    sql_db.session.commit()


#############################################################################
# Register dataset helper functions
#############################################################################

def dataset_info_is_valid(dataset_info):
    """Return True if the dataset info is valid."""

    # Ensure that all the required keys are present.
    for key in DATASET_INFO_REQUIRED_KEYS:
        if key not in dataset_info:
            return False

    # Ensure that it is a "dataset" and not a "protodataset".
    if dataset_info["type"] != "dataset":
        return False

    # Ensure that the UUID has the correct number of characters.
    if len(dataset_info["uuid"]) != 36:
        return False

    # Ensure that the base URI has had any trailing slash removed.
    if dataset_info["base_uri"].endswith("/"):
        return False

    return True


def register_dataset_admin_metadata(admin_metadata):
    """Register the admin metadata in the dataset SQL table."""
    base_uri = get_base_uri_obj(admin_metadata["base_uri"])

    dataset = Dataset(
        uri=admin_metadata["uri"],
        base_uri_id=base_uri.id,
        uuid=admin_metadata["uuid"],
        name=admin_metadata["name"]
    )
    sql_db.session.add(dataset)
    sql_db.session.commit()


def register_dataset_descriptive_metadata(dataset_info):

    # Validate that the base URI exists.
    get_base_uri_obj(dataset_info["base_uri"])

    collection = mongo.db[MONGO_COLLECTION]
    _register_dataset_descriptive_metadata(collection, dataset_info)


def _register_dataset_descriptive_metadata(collection, dataset_info):
    """Register dataset info in the collection.

    If the "uuid" and "uri" are the same as another record in
    the mongodb collection a new record is not created, and
    the UUID is returned.

    Returns None if dataset_info is invalid.
    Returns UUID of dataset otherwise.
    """
    if not dataset_info_is_valid(dataset_info):
        return None

    query = {
        "uuid": dataset_info["uuid"],
        "uri": dataset_info["uri"]
    }

    # If a record with the same UUID and URI exists return the uuid
    # without adding a duplicate record.
    exists = collection.find_one(query)

    if exists is None:
        collection.insert_one(dataset_info)
    else:
        collection.find_one_and_replace(query, dataset_info)

    # The MongoDB client dynamically updates the dataset_info dict
    # with and '_id' key. Remove it.
    if "_id" in dataset_info:
        del dataset_info["_id"]

    return dataset_info["uuid"]


def register_dataset(dataset_info):
    """Register a dataset in the lookup server."""
    if not dataset_info_is_valid(dataset_info):
        raise(ValidationError(
            "Dataset info not valid: {}".format(dataset_info)
        ))

    base_uri = dataset_info["base_uri"]
    if not base_uri_exists(base_uri):
        raise(ValidationError(
            "Base URI is not registered: {}".format(base_uri)
        ))

    if get_admin_metadata_from_uri(dataset_info["uri"]) is None:
        register_dataset_admin_metadata(dataset_info)
    register_dataset_descriptive_metadata(dataset_info)

    return dataset_info["uri"]


#############################################################################
# Dataset information retrieval helper functions.
#############################################################################

def get_admin_metadata_from_uri(uri):
    """Return the dataset SQL table row as dictionary."""
    dataset = Dataset.query.filter_by(uri=uri).first()

    if dataset is None:
        return None

    return dataset.as_dict()


def get_readme_from_uri(uri):
    """Return the readme information."""
    collection = mongo.db[MONGO_COLLECTION]
    item = collection.find_one({"uri": uri})
    return item["readme"]


def list_admin_metadata_in_base_uri(base_uri_str):
    """Return list of dictionaries with admin metadata from dataset SQL table.
    """
    base_uri = get_base_uri_obj(base_uri_str)

    if base_uri is None:
        return None

    return [ds.as_dict() for ds in base_uri.datasets]
