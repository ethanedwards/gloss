import yaml

class promptlibrary:
    def __init__(self, library_path='textcreation/promptlibrary.yml'):
        self.library_path = library_path
        self.prompts = self.load_prompts()

    def load_prompts(self):
        with open(self.library_path) as file:
            prompts = yaml.load(file, Loader=yaml.FullLoader)
        return prompts

    def find_prompt_by_title(self, title):
        for prompt in self.prompts:
            if prompt['title'] == title:
                return prompt['content']
        return None

    @property
    def retry_addendum(self):
        """Get the retry addendum template for failed interlinear entries."""
        return self.find_prompt_by_title('InterlinearRetryAddendum')