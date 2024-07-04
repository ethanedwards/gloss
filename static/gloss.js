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


clickCounts = {};
fetch('/get_click_counts', {
    method: 'GET',
    headers: {
        'Content-Type': 'application/json',
    },
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        clickCounts = data.clicks;
        console.log('Click counts:', clickCounts);
    }
});


let gloss = true;

function lookup(entry){
    // Track click count
    const dictionary = entry.querySelector('.dictionary').textContent.trim();
    const pos = entry.querySelector('.pos').textContent.trim();

    // Send click data to server
    fetch('/update_click', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ lemma: dictionary, pos: pos }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const key = `${dictionary}|${pos}`;
            clickCounts[key] = data.clicks;
            console.log(`Clicked: ${key}, Count: ${clickCounts[key]}`);
        }
    });
}

document.addEventListener('keydown', function(event) {
    if ((event.key === 'a' || event.key === 'A') && event.target.id !== 'studentInput') {
        toggleGloss();
    }
});

document.addEventListener('DOMContentLoaded', (event) => {
    const words = document.querySelectorAll('.word');

    words.forEach(word => {
        word.addEventListener('click', function() {
            const gloss = this.querySelector('.gloss');
            if (gloss) {
                gloss.classList.toggle('permanent-gloss');
                if (gloss.classList.contains('hidden-gloss')) {
                    gloss.classList.remove('hidden-gloss');
                }
            }
            lookup(this);
        });
        word.addEventListener('touchstart', function() {
            const gloss = this.querySelector('.gloss');
            if (gloss) {
                gloss.classList.toggle('permanent-gloss');
                if (gloss.classList.contains('hidden-gloss')) {
                    gloss.classList.remove('hidden-gloss');
                }
            }
            lookup(this);
        });
    });
});

// Prevent the chat interface from losing focus when clicked
document.getElementById('chatInterface').addEventListener('mousedown', function(event) {
    event.preventDefault();
});

document.getElementById('studentInput').addEventListener('mousedown', function(event) {
    event.target.focus();
});

function highlightText(){
    var highlightedText = window.getSelection();
    if (highlightedText) {
        if(getElements(highlightedText)[0] != ""){
            
            currentselection = getElements(highlightedText);
            displayHighlightedText(getElements(highlightedText)[0]);
        }
    }
}

document.addEventListener('mouseup', function() {
    if(!isMobile){
        highlightText();
    }
});

/*
document.addEventListener('touchend', function() {
    highlightText();
});
*/
function displayHighlightedText(text) {
    var highlightedTextElement = document.getElementById('highlightedText');
    highlightedTextElement.textContent = text;
}


// Function to update the highlighted text based on the viewport
function updateHighlightedText() {
    const words = document.querySelectorAll('.word');
    const highlightedWords = [];

    words.forEach(word => {
        if (isElementInViewport(word)) {
            highlightedWords.push(word.textContent.trim());
        }
    });

    currentselection = getElementsMobile(highlightedWords);
    displayHighlightedText(currentselection[0]);
    
}

// Function to check if an element is in the viewport
function isElementInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Create an Intersection Observer
const isMobile = window.innerWidth <= 768; // Check if it's mobile view
if(isMobile){
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                updateHighlightedText();
            }
        });
    }, { threshold: 0.5 }); // Adjust the threshold as needed

    // Observe each word element
    const words = document.querySelectorAll('.word');
    words.forEach(word => {
        observer.observe(word);
    });
}






document.addEventListener('copy', function(event) {
    let selection = window.getSelection();
    if (!selection.rangeCount) return;

    let finalCopyText = getPrompt(getElements(selection));

    if (event.clipboardData) {
        event.preventDefault();
        event.clipboardData.setData('text/plain', finalCopyText);
    } else if (window.clipboardData) {
        window.clipboardData.setData('Text', finalCopyText);
    }
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

function toggleGloss() {
    const glossElements = document.querySelectorAll('.gloss');
    gloss = !gloss;
    glossElements.forEach(function(glossElement) {
        if (gloss) {
            if (!glossElement.classList.contains('permanent-gloss')) {
                glossElement.classList.remove('hidden-gloss');
            }
        } else {
            if (!glossElement.classList.contains('permanent-gloss')) {
                glossElement.classList.add('hidden-gloss');
            }
        }        });
}

document.getElementById('toggleGlossButton').addEventListener('click', function() {
    toggleGloss();
});

function adjustTextareaHeight(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

document.getElementById('studentInput').addEventListener('input', function() {
    adjustTextareaHeight(this);
});

document.getElementById('studentInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('chatForm').dispatchEvent(new Event('submit'));
    }
});


function handleLongPress(element, callback) {
    let timer;
    let touchDuration = 500; // Adjust the duration as needed

    function startLongPress(event) {
        event.preventDefault();
        timer = setTimeout(function() {
            callback(element);
        }, touchDuration);
    }

    function cancelLongPress() {
        if (timer) {
            clearTimeout(timer);
        }
    }

    element.addEventListener('touchstart', startLongPress);
    element.addEventListener('touchend', cancelLongPress);
    element.addEventListener('touchmove', cancelLongPress);
}

document.addEventListener('DOMContentLoaded', (event) => {
    const words = document.querySelectorAll('.word');

    words.forEach(word => {
        word.addEventListener('click', function() {
            const gloss = this.querySelector('.gloss');
            if (gloss && gloss.classList.contains('hidden-gloss')) {
                gloss.classList.remove('hidden-gloss');
            }
        });

        word.addEventListener('touchstart', function() {
            const gloss = this.querySelector('.gloss');
            if (gloss && gloss.classList.contains('hidden-gloss')) {
                gloss.classList.remove('hidden-gloss');
            }
        });

        handleLongPress(word, function() {
            let range = document.createRange();
            range.selectNodeContents(word);
            let selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            displayHighlightedText(getElements(selection)[0]);
        });
    });
});



function getElementsMobile(words) {
    // Iterate over the words array
    let sourceSentences = [];
    let translatedSentences = [];

    // Initialize array to hold the annotated text
    let annotatedText = [];
    let selectedText = []; // This will hold just the selected word strings


    //TODO make this better
    prevword = "";

    words.forEach(word => {
        const wordElements = document.querySelectorAll('.interlinear-container .word');
        wordElements.forEach(wordEl => {
            if (prevword == word) {
                //Repeated word   
            }
            else if (wordEl.textContent.trim() === word) {
                let titleText = wordEl.getAttribute('title') ? wordEl.getAttribute('title').trim() : '';
                let glossText = wordEl.querySelector('.gloss') ? wordEl.querySelector('.gloss').textContent.trim() : '';
                let dictText = wordEl.querySelector('.dictionary') ? wordEl.querySelector('.dictionary').textContent.trim() : '';
                let sourceSent = wordEl.querySelector('.sourcesentence') ? wordEl.querySelector('.sourcesentence').textContent.trim() : '';
                let transSent = wordEl.querySelector('.translation') ? wordEl.querySelector('.translation').textContent.trim() : '';

                let wordTextNodes = Array.from(wordEl.childNodes).filter(node => node.nodeType === Node.TEXT_NODE);
                let wordText = wordTextNodes.map(node => node.textContent.trim()).join(' ');

                // Format the copied data with annotations
                let formattedText = `${wordText} / ${titleText} [${glossText} / ${dictText}]`;
                annotatedText.push(formattedText);

                // Collect just the selected words
                let normalizedWordText = wordText.replace(/\s+/g, ' ').trim();
                selectedText.push(normalizedWordText);

                // Check if sourceSent is in sourceSentences
                if (!sourceSentences.includes(sourceSent)) {
                    sourceSentences.push(sourceSent);
                }
                if (!translatedSentences.includes(transSent)) {
                    translatedSentences.push(transSent);
                }
                prevword = word;
            }
        });
    });

    // Join all pieces of data into strings
    let translatedSentencesJoined = translatedSentences.join(' ');
    let sourceSentencesJoined = sourceSentences.join(' ');
    let annotatedTextJoined = annotatedText.join('**');
    let selectedTextJoined = selectedText.join(' ');
    returnlist = [selectedTextJoined, annotatedTextJoined, sourceSentencesJoined, translatedSentencesJoined];

    return returnlist;
}