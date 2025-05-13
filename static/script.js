const fileInput = document.getElementById('file');
const artistSelect = document.getElementById('artist');
const goButton = document.getElementById('go');
const progressBar = document.getElementById('prog');
const player = document.getElementById('player');
const downloadLinkContainer = document.getElementById('download-link-container');
const statusMessage = document.getElementById('status-message');

async function init() {
    statusMessage.textContent = 'Loading artist list...';
    try {
        const response = await fetch('/artists');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const artists = await response.json();
        
        artistSelect.innerHTML = ''; // Clear existing options
        if (artists.length === 0) {
            const option = new Option('No models found. Please add models to the models folder.', '');
            option.disabled = true;
            artistSelect.add(option);
            statusMessage.textContent = 'No artist models found on server.';
            goButton.disabled = true;
        } else {
            artists.forEach(artist => {
                artistSelect.add(new Option(artist, artist));
            });
            statusMessage.textContent = 'Ready. Select file and artist.';
            goButton.disabled = false;
        }
    } catch (error) {
        console.error('Failed to load artists:', error);
        statusMessage.textContent = 'Failed to load artist list. Check console for errors.';
        artistSelect.innerHTML = '<option value="" disabled>Error loading models</option>';
        goButton.disabled = true;
    }
}

goButton.onclick = async () => {
    const file = fileInput.files[0];
    const artist = artistSelect.value;

    if (!file) {
        statusMessage.textContent = 'Please select an audio file.';
        return;
    }
    if (!artist) {
        statusMessage.textContent = 'Please select an artist.';
        return;
    }

    goButton.disabled = true;
    progressBar.hidden = false;
    progressBar.value = 0;
    player.hidden = true;
    downloadLinkContainer.innerHTML = '';
    statusMessage.textContent = 'Uploading and starting conversion...';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('artist', artist);

    try {
        const convertResponse = await fetch('/convert', {
            method: 'POST',
            body: formData
        });

        if (!convertResponse.ok) {
            const errorData = await convertResponse.json().catch(() => ({ detail: 'Conversion request failed with status: ' + convertResponse.status }));
            throw new Error(errorData.detail || 'Conversion request failed.');
        }

        const { job_id } = await convertResponse.json();
        statusMessage.textContent = `Processing job: ${job_id}. Please wait...`;
        progressBar.value = 25; // Simulate some progress

        let resultUrl = null;
        let jobDone = false;
        let attempts = 0;
        const maxAttempts = 60; // Poll for 2.5 * 60 = 150 seconds max

        while (!jobDone && attempts < maxAttempts) {
            attempts++;
            progressBar.value = 25 + (attempts / maxAttempts) * 50; // Progress from 25% to 75%
            
            const resultResponse = await fetch(`/result/${job_id}`);
            if (!resultResponse.ok) {
                 // If 404, job might not exist or was entered wrong, but server should give other errors for that
                statusMessage.textContent = `Waiting for result (attempt ${attempts})...`;
                await new Promise(resolve => setTimeout(resolve, 2500)); // Wait 2.5 seconds
                continue;
            }

            // Check content type first for audio
            const contentType = resultResponse.headers.get('Content-Type');
            if (contentType && contentType.startsWith('audio')) {
                const blob = await resultResponse.blob();
                resultUrl = URL.createObjectURL(blob);
                jobDone = true;
                progressBar.value = 100;
                statusMessage.textContent = 'Conversion successful!';
            } else {
                // If not audio, it should be JSON with status
                const jobStatus = await resultResponse.json();
                if (jobStatus.status === 'completed') { // Should have been caught by audio check
                    // This state implies an issue, perhaps file gone after completion
                    statusMessage.textContent = 'Error: Conversion reported complete but no audio received.';
                    jobDone = true; // break loop
                } else if (jobStatus.status === 'failed') {
                    statusMessage.textContent = `Conversion failed: ${jobStatus.error || 'Unknown error'}`;
                    jobDone = true; // break loop
                } else if (jobStatus.status === 'processing') {
                    statusMessage.textContent = `Still processing (attempt ${attempts})...`;
                    await new Promise(resolve => setTimeout(resolve, 2500));
                } else {
                    statusMessage.textContent = `Unknown job status: ${jobStatus.status}. Retrying...`;
                    await new Promise(resolve => setTimeout(resolve, 2500));
                }
            }
        }

        progressBar.hidden = true;
        goButton.disabled = false;

        if (resultUrl) {
            player.src = resultUrl;
            player.hidden = false;

            const a = document.createElement('a');
            a.href = resultUrl;
            a.download = `converted_${artist}_${file.name}`;
            a.textContent = 'Download Converted Song';
            downloadLinkContainer.appendChild(a);
        } else if (!jobDone) {
            statusMessage.textContent = 'Conversion timed out. Please try again or check server logs.';
        } else if (statusMessage.textContent === `Processing job: ${job_id}. Please wait...` || statusMessage.textContent.startsWith('Still processing')){
             // If loop finished due to maxAttempts but status was still processing
             statusMessage.textContent = 'Conversion timed out or server is busy. Please try again later.';
        }

    } catch (error) {
        console.error('Conversion process error:', error);
        statusMessage.textContent = `Error: ${error.message}`;
        progressBar.hidden = true;
        goButton.disabled = false;
    }
};

// Initialize the page
init(); 