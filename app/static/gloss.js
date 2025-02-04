var currentselection = "";
var autoHighlight = false;
let filename = document.querySelector('meta[name="sentence_store"]').content;

function generateTutorResponse(studentText) {
    return new Promise((resolve, reject) => {
        var context = "";
        //var highlightedText = window.getSelection();
        try{
            if (currentselection.length > 0 && !autoHighlight){
                context = getPrompt(currentselection);
            }
            // If no selection, use text from whole window
            else{
                updateHighlightedText();
                context = getPrompt(currentselection);
                // Turn on autohighlight mode assuming the user can't use normal highlighting (iPad)
                autoHighlight = true;
            }
        } catch (error) {
            console.error('Error geting prompt:', error);
            context = "";
        }

        prompt = context + "\n" + studentText;
        tutorRequest(prompt)
            .then(() => {
                resolve();
            })
            .catch(error => {
                console.error('Error generating tutor response:', error);
                reject(error);
            });
    });
}

function tutorRequest(prompt) {
    const requestData = {
        content: prompt,
    };
    // get the text name by joining all elements of the split filename except the last one
    textname = filename.split('_').slice(0, -1).join('_');
    return fetch(`/api/chatresponse?textname=${textname}`, {
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

/*
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
*/

let gloss = true;

function lookup(entry){
    // Track click count
    const dictionary = entry.querySelector('.dictionary').textContent.trim();
    const pos = entry.querySelector('.pos').textContent.trim();

    // Send click data to server
    /*
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
    */
}

document.addEventListener('keydown', function(event) {
    if ((event.key === 'a' || event.key === 'A') && event.target.id !== 'studentInput') {
        toggleGloss();
    }
});

// Replace the existing word-specific event listeners with this:
document.addEventListener('DOMContentLoaded', (event) => {
    // Add a single event listener to the interlinear container
    const container = document.querySelector('.interlinear-container');
    
    // Handle clicks/touches
    container.addEventListener('click', handleWordInteraction);
    container.addEventListener('touchstart', handleWordInteraction);
    
    // Add IDs to all words
    const words = document.querySelectorAll('.word');
    words.forEach((word, index) => {
        word.setAttribute('data-word-id', `word-${index}`);
    });
});

function handleWordInteraction(event) {
    const wordElement = event.target.closest('.word');
    if (!wordElement) return; // Exit if click/touch wasn't on a word
    
    const gloss = wordElement.querySelector('.gloss');
    if (gloss) {
        gloss.classList.toggle('permanent-gloss');
        if (gloss.classList.contains('hidden-gloss')) {
            gloss.classList.remove('hidden-gloss');
        }
    }
    lookup(wordElement);
}

// For long press functionality, modify the handleLongPress implementation:
const longPressManager = {
    timer: null,
    touchDuration: 500,
    
    init() {
        const container = document.querySelector('.interlinear-container');
        container.addEventListener('touchstart', this.handleTouchStart.bind(this));
        container.addEventListener('touchend', this.handleTouchEnd.bind(this));
        container.addEventListener('touchmove', this.handleTouchEnd.bind(this));
    },
    
    handleTouchStart(event) {
        const wordElement = event.target.closest('.word');
        if (!wordElement) return;
        
        event.preventDefault();
        this.timer = setTimeout(() => {
            let range = document.createRange();
            range.selectNodeContents(wordElement);
            let selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            displayHighlightedText(getElements(selection)[0]);
        }, this.touchDuration);
    },
    
    handleTouchEnd() {
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
    }
};

// Initialize long press functionality
document.addEventListener('DOMContentLoaded', () => {
    longPressManager.init();
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
    // Check if there is any selection and it's not empty
    if (highlightedText.toString().length > 0){
        if(getElements(highlightedText)[0] != ""){
            // Turn off autohighlight mode because the user is using normal highlighting
            autoHighlight = false;
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
    if(sentenceStoreLoaded){
        currentselection = getElementsMobile(highlightedWords);
        displayHighlightedText(currentselection[0]);
    }
    
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




// Load sentence data when page loads
let sentenceStore = {};
var sentenceStoreLoaded = false;

// get filename from html, then pass it to fetch request
fetch(`/texts/get_sentence_data?filename=${filename}`)
    .then(response => response.json())
    .then(data => {
        sentenceStore = data;
        sentenceStoreLoaded = true;
    });

function getElements(selection) {
    if (!selection.rangeCount) return;

    let range = selection.getRangeAt(0);
    let container = document.createElement('div');
    container.appendChild(range.cloneContents());

    let sentenceIds = new Set();
    let annotatedText = [];
    let selectedText = [];

    container.querySelectorAll('.word').forEach(wordEl => {
        const wordId = wordEl.dataset.wordId;
        const sentenceId = wordEl.dataset.sentenceId;
        
        sentenceIds.add(sentenceId);

        let titleText = wordEl.getAttribute('title') || '';
        let glossText = wordEl.querySelector('.gloss')?.textContent.trim() || '';
        let dictText = wordEl.querySelector('.dictionary')?.textContent.trim() || '';

        let wordTextNodes = Array.from(wordEl.childNodes)
            .filter(node => node.nodeType === Node.TEXT_NODE);
        let wordText = wordTextNodes.map(node => node.textContent.trim()).join(' ');

        let formattedText = `${wordText} / ${titleText} [${glossText} / ${dictText}]`;
        annotatedText.push(formattedText);
        selectedText.push(wordText.replace(/\s+/g, ' ').trim());
    });

    // Get sentences from store
    let sourceSentences = [];
    let translatedSentences = [];
    
    sentenceIds.forEach(id => {
        if (sentenceStore.sentences[id]) {
            sourceSentences.push(sentenceStore.sentences[id].source);
            translatedSentences.push(sentenceStore.sentences[id].translation);
        }
    });

    return [
        selectedText.join(' '),
        annotatedText.join('**'),
        sourceSentences.join(' '),
        translatedSentences.join(' ')
    ];
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
        // Get current page information from URL
        const currentPath = window.location.pathname;
        const pathParts = currentPath.split('/');
        const textName = pathParts[pathParts.length - 2];
        const currentPage = parseInt(pathParts[pathParts.length - 1]);
        //Log current page with "current page: "
    
        // Get navigation buttons
        const prevButton = document.getElementById('prevPageButton');
        const nextButton = document.getElementById('nextPageButton');
    
        // Initialize navigation buttons
        async function initializeNavigation() {
            const prevPage = document.querySelector('meta[name="previous_page"]')?.content;
            const nextPage = document.querySelector('meta[name="next_page"]')?.content;
            // Check if previous page exists
            if (prevPage) {
                prevButton.style.display = 'block';
                prevButton.addEventListener('click', () => {
                    window.location.href = `/texts/${textName}/${prevPage}`;
                });
            }
    
            // Check if next page exists
            if (nextPage) {
                nextButton.style.display = 'block';
                nextButton.addEventListener('click', () => {
                    window.location.href = `/texts/${textName}/${nextPage}`;
                });
            }
        }
    
        initializeNavigation();




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

    // Initialize array to hold the annotated text
    let annotatedText = [];
    let selectedText = []; // This will hold just the selected word strings

    let sentenceIds = new Set();


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
                let wordTextNodes = Array.from(wordEl.childNodes).filter(node => node.nodeType === Node.TEXT_NODE);
                let wordText = wordTextNodes.map(node => node.textContent.trim()).join(' ');

                // Format the copied data with annotations
                let formattedText = `${wordText} / ${titleText} [${glossText} / ${dictText}]`;
                annotatedText.push(formattedText);

                const sentenceId = wordEl.dataset.sentenceId;
                sentenceIds.add(sentenceId);

                // Collect just the selected words
                let normalizedWordText = wordText.replace(/\s+/g, ' ').trim();
                selectedText.push(normalizedWordText);

                prevword = word;
            }
        });
    });

    // Get sentences from store
    let sourceSentences = [];
    let translatedSentences = [];
    
    sentenceIds.forEach(id => {
        if (sentenceStore.sentences[id]) {
            sourceSentences.push(sentenceStore.sentences[id].source);
            translatedSentences.push(sentenceStore.sentences[id].translation);
        }
    });


    // Join all pieces of data into strings
    let translatedSentencesJoined = translatedSentences.join(' ');
    let sourceSentencesJoined = sourceSentences.join(' ');
    let annotatedTextJoined = annotatedText.join('**');
    let selectedTextJoined = selectedText.join(' ');
    returnlist = [selectedTextJoined, annotatedTextJoined, sourceSentencesJoined, translatedSentencesJoined];

    return returnlist;
}