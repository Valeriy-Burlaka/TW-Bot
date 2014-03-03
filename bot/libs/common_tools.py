import shelve


class Storage:
    """
    Delegates save & update operations to one of storage-helpers
    """

    def __init__(self, storage_type, storage_name):
        if storage_type == 'local_file':
            self.storage_processor = LocalStorage(storage_name)
        else:
            raise NotImplementedError("Specified storage type for map data"
                                      "is not implemented yet!")

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            if not hasattr(self.storage_processor, name):
                raise NotImplementedError
            else:
                return getattr(self.storage_processor, name)(*args, **kwargs)
        return wrapper


class LocalStorage:
    """
    Handles retrieval & update of data saved in a local file.

    Methods:

    get_saved_villages:
        returns villages that were saved in a local shelve file
    update_villages(villages):
        updates information about (attacked) villages in a local
        shelve file
    save_attacks(arrivals, returns):
        saves given arrivals & returns in a local shelve file
    get_saved_arrivals:
        returns arrivals that were saved in a local shelve file
    get_saved_returns:
        returns 'returns', ye.
    """

    def __init__(self, storage_name):
        self.storage_name = storage_name

    def get_saved_villages(self):
        storage = shelve.open(self.storage_name)
        saved_villages = storage.get('villages', {})
        storage.close()
        return saved_villages

    def update_villages(self, villages):
        storage = shelve.open(self.storage_name)
        saved_villages = storage.get('villages', {})
        saved_villages.update(villages)

        storage['villages'] = saved_villages
        storage.close()

    def save_attacks(self, arrivals=None, returns=None):
        storage = shelve.open(self.storage_name)
        if arrivals:
            storage['arrivals'] = arrivals
        if returns:
            storage['returns'] = returns
        storage.close()

    def get_saved_arrivals(self):
        storage = shelve.open(self.storage_name)
        arrivals = storage.get('arrivals', {})
        storage.close()
        return arrivals

    def get_saved_returns(self):
        storage = shelve.open(self.storage_name)
        returns = storage.get('returns', {})
        storage.close()
        return returns
