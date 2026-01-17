const fs = require('fs');
const path = require('path');

/**
 * Note: Since GitHub Actions runs in a Node environment, 
 * we use 'node-fetch' for API requests.
 */
const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));

// --- CONFIGURATION ---
const featuredTeamsList = [
    "al-nassr", "inter miami cf", "fc-bayern-munchen", "dortmund", "leverkusen", 
    "paris-saint-germain", "juventus", "atletico-madrid", "barcelona", "real madrid", 
    "arsenal", "chelsea", "manchester city", "manchester united", "liverpool",
    "portugal", "argentina", "brazil", "spain", "england", "france", "inter", "milan"
];

const API_BASE = "https://www.sofascore.com/api/v1";
const API_HIGHLIGHTS = "https://api.sofascore.com/api/v1";

// --- UTILITIES ---
function generateCustomID() {
    const letters = "abcdefghijklmnopqrstuvwxyz";
    const numbers = "0123456789";
    let res = "";
    for (let i = 0; i < 4; i++) res += letters.charAt(Math.floor(Math.random() * letters.length));
    for (let i = 0; i < 6; i++) res += numbers.charAt(Math.floor(Math.random() * numbers.length));
    return res;
}

function cleanTeamName(name) {
    return name.replace(/-/g, ' ').replace(/\bFC\b/gi, '').trim();
}

// --- MAIN ENGINE ---
async function startExtraction() {
    const today = new Date().toISOString().split('T')[0];
    console.log(`🚀 Starting Extraction for: ${today}`);

    try {
        // 1. Fetch all football events for today
        const response = await fetch(`${API_BASE}/sport/football/scheduled-events/${today}`);
        const data = await response.json();
        
        if (!data.events) {
            console.log("No events found for today.");
            return;
        }

        // 2. Filter for finished/ended matches
        const finishedMatches = data.events.filter(m => {
            const status = m.status.type.toLowerCase();
            return status === 'finished' || status === 'ended';
        });

        console.log(`✅ Found ${finishedMatches.length} finished matches.`);

        let priorityQueue = [];
        let standardQueue = [];

        // 3. Process matches and check for highlights
        for (const match of finishedMatches) {
            const hName = match.homeTeam.name.toLowerCase();
            const aName = match.awayTeam.name.toLowerCase();
            
            // Check if it's a Top Team
            const isTopTeam = featuredTeamsList.some(team => hName.includes(team) || aName.includes(team));

            try {
                const hRes = await fetch(`${API_HIGHLIGHTS}/event/${match.id}/highlights`);
                const hData = await hRes.json();

                if (hData.highlights && hData.highlights.length > 0) {
                    // Extract the best YouTube link
                    let ytLink = null;
                    for (const h of hData.highlights) {
                        const subtitle = (h.subtitle || "").toLowerCase();
                        if (subtitle.includes("highlights") || subtitle.includes("extended")) {
                            const url = h.url || h.sourceUrl || '';
                            const ytMatch = url.match(/(?:v=|\/|vi\/|embed\/)([A-Za-z0-9_-]{11})/);
                            if (ytMatch) {
                                ytLink = `https://www.youtube.com/watch?v=${ytMatch[1]}`;
                                break; 
                            }
                        }
                    }

                    if (ytLink) {
                        const highlightObj = {
                            id: generateCustomID(),
                            team1: cleanTeamName(match.homeTeam.name),
                            team2: cleanTeamName(match.awayTeam.name),
                            category: match.tournament.name,
                            date: today,
                            link: ytLink,
                            isPriority: isTopTeam
                        };

                        if (isTopTeam) {
                            priorityQueue.push(highlightObj);
                        } else {
                            standardQueue.push(highlightObj);
                        }
                    }
                }
            } catch (err) {
                console.error(`Error fetching highlights for ID ${match.id}:`, err.message);
            }
        }

        // 4. Merge: Priority Teams first, then the rest
        const finalHighlights = [...priorityQueue, ...standardQueue];

        // 5. Ensure directory exists and save
        const apiDir = path.join(__dirname, '../api');
        if (!fs.existsSync(apiDir)) {
            fs.mkdirSync(apiDir, { recursive: true });
        }

        fs.writeFileSync(
            path.join(apiDir, 'highlights.json'),
            JSON.stringify(finalHighlights, null, 2)
        );

        console.log(`🏁 Success! Generated highlights.json with ${finalHighlights.length} items.`);
        console.log(`🔥 Top Team Matches included: ${priorityQueue.length}`);

    } catch (globalError) {
        console.error("Fatal Script Error:", globalError);
        process.exit(1);
    }
}

startExtraction();
