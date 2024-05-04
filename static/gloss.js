var currentselection = "a";

function generateTutorResponse(studentText) {
    return new Promise((resolve, reject) => {
        var context = "";
        //var highlightedText = window.getSelection();
        try{
            context = getPrompt(currentselection);
        } catch (error) {
            console.error('Error geting prompt:', error);
            context = "";
        }

        var system = "You are an German tutor, who explains the language to learners interested in reading literature in the language. You assume your students are familiar with grammatical terms in general, though not specifically German. You explain in detail and handle special cases. Student questions will often ask about specific phrases, which you will be given the context of, including the results of an automatic grammatical parser.";

        prompt = context + "\n" + studentText;
        tutorRequest(prompt, system)
            .then(() => {
                resolve();
            })
            .catch(error => {
                console.error('Error generating tutor response:', error);
                reject(error);
            });
    });
}

function tutorRequest(prompt, system) {
    const requestData = {
        content: prompt,
    };
    return fetch('/chatresponse', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        function readStream() {
            return reader.read().then(({ done, value }) => {
                if (done) {
                    return;
                }

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data:')) {
                        const data = JSON.parse(line.substring(5));
                        addChatMessage('tutor', data.text, true); // Append the text to the existing message
                    }
                }

                return readStream();
            });
        }

        return readStream();
    });
}

document.getElementById('chatForm').addEventListener('submit', function (e) {
    e.preventDefault(); // Prevents form from refreshing the page
    const studentText = document.getElementById('studentInput').value;
    
    if (studentText.trim() !== "") {
        addChatMessage('student', studentText);
        generateTutorResponse(studentText)
            .then(() => {
                document.getElementById('studentInput').value = ''; // Reset input field
            })
            .catch(error => {
                console.error('Error generating tutor response:', error);
                // Handle the error appropriately (e.g., display an error message to the user)
            });
    }
});

function addChatMessage(sender, text, append = false) {
    const chatInterface = document.getElementById('chatInterface');
    let messageDiv;

    if (append && sender === 'tutor') {
        messageDiv = chatInterface.querySelector('.chat-message.tutor:last-child');
        if (messageDiv) {
            const textDiv = messageDiv.querySelector('.message-text');
            textDiv.innerHTML += text; // Append the new text to the existing message
        } else {
            messageDiv = null; // Create a new message if there is no existing tutor message
        }
    }

    if (!messageDiv) {
        messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${sender}`;
        
        const senderDiv = document.createElement('div');
        senderDiv.className = 'sender';
        senderDiv.textContent = sender.charAt(0).toUpperCase() + sender.slice(1) + ':';
        
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerHTML = text; // Use innerHTML carefully to ensure text is properly escaped if coming from users
        
        messageDiv.appendChild(senderDiv);
        messageDiv.appendChild(textDiv);
        chatInterface.appendChild(messageDiv);
    }
    
    chatInterface.scrollTop = chatInterface.scrollHeight; // Scroll to latest message
}





let gloss = false;

document.addEventListener('keydown', function(event) {
    // Check if the pressed key is 'a' or 'A' and the target is not the input field
    if ((event.key === 'a' || event.key === 'A') && event.target.id !== 'studentInput') {
        const glossElements = document.querySelectorAll('.gloss');
        gloss = !gloss;
        glossElements.forEach(function(glossElement) {
            if (gloss) {
                glossElement.classList.remove('hidden-gloss');
            } else {
                glossElement.classList.add('hidden-gloss');
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', (event) => {
    const words = document.querySelectorAll('.word');

    words.forEach(word => {
        word.addEventListener('click', function() {
            const gloss = this.querySelector('.gloss');
            if (gloss && gloss.classList.contains('hidden-gloss')) {
                gloss.classList.remove('hidden-gloss');
            }
        });
    });
});

document.addEventListener('mouseup', function() {
    var highlightedText = window.getSelection();
    if (highlightedText) {
        if(getElements(highlightedText)[0] != ""){
            
            currentselection = getElements(highlightedText);
            displayHighlightedText(getElements(highlightedText)[0]);
        }
    }
});

function displayHighlightedText(text) {
    var container = document.getElementById('highlightedTextContainer');
    container.textContent = text;
}

document.addEventListener('copy', function(event) {
    let selection = window.getSelection();
    if (!selection.rangeCount) return;

    let finalCopyText = getPrompt(getElements(selection));

    event.preventDefault();
    event.clipboardData.setData('text/plain', finalCopyText);
});

// Prevent the chat interface from losing focus when clicked
document.getElementById('chatInterface').addEventListener('mousedown', function(event) {
    event.preventDefault();
});

document.getElementById('studentInput').addEventListener('mousedown', function(event) {
    event.target.focus();
});


function getElements(selection){
    if (!selection.rangeCount) return; // No selection, exit

    // Get the selected range and create a container element to hold the selection contents
    let range = selection.getRangeAt(0);
    let container = document.createElement('div');
    container.appendChild(range.cloneContents());

    // Initialize arrays to hold the source and translated sentences
    let sourceSentences = [];
    let translatedSentences = [];

    // Initialize array to hold the annotated text
    let annotatedText = [];
    let selectedText = []; // This will hold just the selected word strings

    // Iterate over '.word' elements inside the selection
    // container.querySelectorAll('.word').forEach(wordEl => {
        
    //     let titleText = wordEl.getAttribute('title') ? wordEl.getAttribute('title').trim() : '';
    //     let glossText = wordEl.querySelector('.gloss') ? wordEl.querySelector('.gloss').textContent.trim() : '';
    //     let dictText = wordEl.querySelector('.dictionary') ? wordEl.querySelector('.dictionary').textContent.trim() : '';
    //     let sourceSent = wordEl.querySelector('.sourcesentence') ? wordEl.querySelector('.sourcesentence').textContent.trim() : '';
    //     let transSent = wordEl.querySelector('.translation') ? wordEl.querySelector('.translation').textContent.trim() : '';]
    container.querySelectorAll('.word').forEach(wordEl => {
        

        let titleText = wordEl.getAttribute('title') ? wordEl.getAttribute('title').trim() : '';
        let glossText = wordEl.querySelector('.gloss') ? wordEl.querySelector('.gloss').textContent.trim() : '';
        let dictText = wordEl.querySelector('.dictionary') ? wordEl.querySelector('.dictionary').textContent.trim() : '';
        let sourceSent = wordEl.querySelector('.sourcesentence') ? wordEl.querySelector('.sourcesentence').textContent.trim() : '';
        let transSent = wordEl.querySelector('.translation') ? wordEl.querySelector('.translation').textContent.trim() : '';

        //TODO Weird glitch when selecting the last word only partially, does get any content other than word or title like the sentences
        //Fixes have been weird

        let wordTextNodes = Array.from(wordEl.childNodes).filter(node => node.nodeType === Node.TEXT_NODE);
        let wordText = wordTextNodes.map(node => node.textContent.trim()).join(' ');


        //console.log("Elements of formatted are word text " + wordText + " \ntitletext " + titleText + " \nglossText " + glossText + " \ndictText " + dictText);
        // Format the copied data with annotations
        let formattedText = `${wordText} / ${titleText} [${glossText} / ${dictText}]`;
        annotatedText.push(formattedText);

        //console.log("word text is " + wordText + "end word text");
        
        // Collect just the selected words
        let normalizedWordText = wordText.replace(/\s+/g, ' ').trim();
        selectedText.push(normalizedWordText);


        //Check if sourceSent is in sourceSentences

        if (!sourceSentences.includes(sourceSent)) {
            sourceSentences.push(sourceSent);
        }
        if (!translatedSentences.includes(transSent)) {
            translatedSentences.push(transSent);
        }
    });

    // Join all pieces of data into strings
    //console.log(translatedSentences);
    //console.log(sourceSentences);
    let translatedSentencesJoined = translatedSentences.join(' ');
    let sourceSentencesJoined = sourceSentences.join(' ');
    let annotatedTextJoined = annotatedText.join('**');
    let selectedTextJoined = selectedText.join(' ');

returnlist = [selectedTextJoined, annotatedTextJoined, sourceSentencesJoined, translatedSentencesJoined];

return returnlist;
}

function getPrompt(elements){
    
    let finalCopyText = `Translated sentences: ${elements[3]}
    Source sentences: ${elements[2]}
    
    Annotated text: ${elements[1]}
    
    Selected text: ${elements[0]}
    `;
    return finalCopyText;
}