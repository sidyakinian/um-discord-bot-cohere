from managers.FirebaseManager import FirebaseManager

class MessageSender(object):

    def __init__(self, firebase_manager):
        self.firebase_manager = firebase_manager

    async def send_message_from_ctx(self, ctx, message, file=None):
        await self.firebase_manager.log_message(str(ctx.author.id), message, False)
        await ctx.send(message, file=file)
    
    async def send_message_from_author(self, author, message, file=None):
        await self.firebase_manager.log_message(str(author.id), message, False)
        await author.send(message, file=file)
    