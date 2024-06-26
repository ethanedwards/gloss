class llm:
    def __init__(self, name):
        self.name = name

    def get_completion_sync(messages:dict, model:str, max_tokens:int=1024, temperature:float=0.8):
        """
        Get the declension of a noun.
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")
    
    async def get_completion_async(messages:dict, model:str, max_tokens:int=1024, temperature:float=0.8):
        """
        Completion
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")

    def format_messages(userprompt:str, systemprompt:str):
        raise NotImplementedError("This method should be implemented by subclass.")
    
    def format_messages_buffer(buffer:list, systemprompt:str):
        raise NotImplementedError("This method should be implemented by subclass.")