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

function addChatMessage(sender, text) {
    const chatInterface = document.getElementById('chatInterface');
    const newMessageDiv = document.createElement('div');
    newMessageDiv.className = 'chat-message';
    
    const senderDiv = document.createElement('div');
    senderDiv.className = sender;
    senderDiv.textContent = sender.charAt(0).toUpperCase() + sender.slice(1) + ':';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.innerHTML = text; // Use innerHTML carefully to ensure text is properly escaped if coming from users
    
    newMessageDiv.appendChild(senderDiv);
    newMessageDiv.appendChild(textDiv);
    chatInterface.appendChild(newMessageDiv);
    
    chatInterface.scrollTop = chatInterface.scrollHeight; // Scroll to latest message
}

function generateTutorResponse(studentText) {
    return new Promise((resolve, reject) => {
        var context = "";
        var highlightedText = window.getSelection();
        
        if (highlightedText) {
            context = getPrompt(highlightedText);
            console.log(context);
        }
        console.log(context);

        var system = "You are an German tutor, who explains the language to learners interested in reading literature in the language. You assume your students are familiar with grammatical terms in general, though not specifically German. You explain in detail and handle special cases. Student questions will often ask about specific phrases, which you will be given the context of, including the results of an automatic grammatical parser.";

        prompt = context + "\n" + studentText;
        tutorRequest(prompt, system)
            .then(tutorResponse => {
                console.log(tutorResponse);
                addChatMessage('tutor', tutorResponse);
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
    .then(response => response.json())
    .then(data => {
        console.log('Response:', data);
        return data.response;
    });
}



var gloss = true;
document.addEventListener('keydown', function(event) {
    // Check if the pressed key is 'a' or 'A'
    if (event.key === 'a' || event.key === 'A') {
        // Select all elements with the class name 'gloss'
        const glossElements = document.querySelectorAll('.gloss');
        gloss = !gloss;
        // Toggle the 'hidden-gloss' class for each gloss element
        glossElements.forEach(function(glossElement) {
            if (glossElement.classList.contains('hidden-gloss')) {
                // If the gloss is hidden (transparent), remove the class to show it
                glossElement.classList.remove('hidden-gloss');
            } else {
                // If the gloss is shown, add the class to hide it
                glossElement.classList.add('hidden-gloss');
            }
            if(gloss){
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
            // Get the .gloss element within the clicked .word
            const gloss = this.querySelector('.gloss');
            if (gloss && gloss.classList.contains('hidden-gloss')) {
                // Make .gloss visible (by removing 'hidden-gloss' class) if it is hidden
                gloss.classList.remove('hidden-gloss');
            } else {
                // Optionally, hide .gloss again if it was already visible
                // gloss.classList.add('hidden-gloss'); // Uncomment this line if needed
            }
        });
    });
});

document.addEventListener('mouseup', function() {
    var highlightedText = window.getSelection();
    if (highlightedText) {
      displayHighlightedText(getElements(highlightedText)[0]);
    }
  });

function displayHighlightedText(text) {
    var container = document.getElementById('highlightedTextContainer');
    container.textContent = text; // Update the container with the highlighted text
  }
  
  document.addEventListener('copy', function(event) {
    let selection = window.getSelection();
    if (!selection.rangeCount) return; // No selection, exit

    // Create the final output text
let finalCopyText = getPrompt(selection);

    // Prevent the default copy action
    event.preventDefault();

    // Set the final text as the clipboard data
    event.clipboardData.setData('text/plain', finalCopyText);
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

function getPrompt(selection){
    
    elements = getElements(selection);
    let finalCopyText = `Translated sentences: ${elements[3]}
    Source sentences: ${elements[2]}
    
    Annotated text: ${elements[1]}
    
    Selected text: ${elements[0]}
    `;
    return finalCopyText;
}