import os
from dotenv import load_dotenv
import uuid
from datetime import datetime

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

load_dotenv()
FIREBASE_CERTIFICATE_FILEPATH = os.environ['FIREBASE_CERTIFICATE_FILEPATH']

class FirebaseManager(object):
    def __init__(self):
        cred = credentials.Certificate(FIREBASE_CERTIFICATE_FILEPATH)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    async def all_puzzles(self):
        docs = self.db.collection(u'puzzles').stream()
        doc_data_array = [doc.to_dict() for doc in docs]
        return sorted(filter(lambda doc: doc['id'] != 0, doc_data_array), key=lambda doc: doc['id'])

    async def add_user_state(self, user_id):
        self.db.collection(u'user_states').document(user_id).set({
            "puzzle_id": 1,
            "state_name": "tutorial_welcome",
            "hints_given": 0,
        })

    async def delete_user_state(self, user_id):
        self.db.collection(u'user_states').document(user_id).delete()

    async def set_to_playing(self, user_id, puzzle_id):
        self.db.collection(u'user_states').document(user_id).set({
            "puzzle_id": puzzle_id,
            "state_name": "playing",
            "hints_given": 0,
        })

    async def set_to_idle(self, user_id):
        self.db.collection(u'user_states').document(user_id).set({
            "puzzle_id": -1,
            "state_name": "idle",
            "hints_given": 0,
        })

    async def set_to_tutorial(self, user_id, state_name):
        self.db.collection(u'user_states').document(user_id).set({
            "puzzle_id": 1,
            "state_name": state_name,
            "hints_given": 0,
        })

    async def increment_hint(self, user_id):
        state_name, puzzle_id, hints_given = await self.state(user_id)
        if state_name != "playing":
            print('Warning: user state is idle, but still incrementing hint')
        self.db.collection(u'user_states').document(user_id).set({
            "puzzle_id": puzzle_id,
            "state_name": "playing",
            "hints_given": hints_given + 1,
        })

    async def log_message(self, user_id, message, is_from_user):
        local_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timestamp = firestore.SERVER_TIMESTAMP
        author = "user" if is_from_user else "bot"
        self.db.collection(u'users').document(user_id).collection(u'messages').document(str(uuid.uuid4())).set({
            "message": message,
            "author": author,
            "timestamp": timestamp,
            "local_timestamp": local_timestamp,
        })

    async def add_feedback(self, user_id, message):
        local_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timestamp = firestore.SERVER_TIMESTAMP
        self.db.collection(u'users').document(user_id).collection(u'feedback').document(str(uuid.uuid4())).set({
            "message": message,
            "timestamp": timestamp,
            "local_timestamp": local_timestamp,
        })

    async def puzzle_data(self, puzzle_id):
        docs = self.db.collection(u'puzzles').where(u'id', u'==', int(puzzle_id)).stream()
        try:
            doc = next(docs)
        except StopIteration:
            # TODO: log this in Amplitude
            print(f'puzzle_data doesn\'t exist for id {int(puzzle_id)}')
            raise Exception(f'puzzle_data doesn\'t exist for id {int(puzzle_id)}')
        doc_data = doc.to_dict()
        return doc_data

    async def state(self, user_id):
        doc_ref = self.db.collection(u'user_states').document(user_id)
        doc = doc_ref.get()
        if doc.exists == False:
            # TODO: log this in Amplitude
            raise Exception(f'user_state document doesn\'t exist for user_id {user_id}')
        else:
            state = doc.to_dict()
            state_name = state["state_name"]
            puzzle_id = state["puzzle_id"]
            hints_given = state["hints_given"]
            return (state_name, puzzle_id, hints_given)

    async def puzzle_document_id(self, puzzle_id):
        docs = self.db.collection(u'puzzles').where(u'id', u'==', puzzle_id).stream()
        doc = next(docs)
        return doc.id
