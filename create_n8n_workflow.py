"""
create_n8n_workflow.py
Generates the complete, production-ready n8n workflow JSON for Mielen Voima Long Videos.
Includes: Daily Schedule, Google Sheet fetch, Render engine dispatch, Polling,
Downloading 1080p MP4 and 1280x720 Thumbnail, YouTube Video upload, YouTube Custom Thumbnail upload (OAuth),
Google Sheet update, and Telegram notifications.
"""

import json
import uuid
from pathlib import Path

def uid():
    return str(uuid.uuid4())

nodes = [
    {
        "parameters": {
            "rule": {
                "interval": [
                    {
                        "field": "cronExpression",
                        "expression": "0 16 * * *"
                    }
                ]
            }
        },
        "id": "node-trigger-daily",
        "name": "⏰ Daily Schedule Trigger (19:00 FI / 21:30 IST)",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [-1600, 400]
    },
    {
        "parameters": {
            "jsCode": "const staticData = $getWorkflowStaticData('global');\nstaticData.healthCheckAttempts = 0;\nstaticData.pollAttempts = 0;\nreturn $input.all();"
        },
        "id": "node-reset-counters",
        "name": "🔁 Reset Poll Counters",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-1380, 400]
    },
    {
        "parameters": {
            "url": "https://mielen-voima-long-video-engine.onrender.com/health",
            "options": {
                "timeout": 45000
            }
        },
        "id": "node-wake-render",
        "name": "🔔 Wake Render Engine (GET /health)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [-1160, 400],
        "continueOnFail": True
    },
    {
        "parameters": {
            "amount": 45
        },
        "id": "node-wait-spinup",
        "name": "⏳ Wait for Render Spin-up (45s)",
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [-940, 400],
        "webhookId": uid()
    },
    {
        "parameters": {
            "documentId": {
                "__rl": True,
                "value": "13ZSBJQrevEo2lJqZ_LoTLyJ_6sEKjHFwhauqmHTamoc",
                "mode": "list"
            },
            "sheetName": {
                "__rl": True,
                "value": 1374005491,
                "mode": "list"
            },
            "filtersUI": {
                "values": [
                    {
                        "lookupColumn": "Status",
                        "lookupValue": "pending"
                    }
                ]
            },
            "options": {}
        },
        "id": "node-sheet-get",
        "name": "📊 Get Today Long Video Script from Sheet",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [-720, 400],
        "credentials": {
            "googleSheetsOAuth2Api": {
                "id": "ew6mItBZu7P6dspU",
                "name": "Google Sheets account 100 account"
            }
        }
    },
    {
        "parameters": {
            "jsCode": """
const inputRows = $input.all().map(i => i.json);
if (!inputRows || inputRows.length === 0) {
  throw new Error("Mielen Voima: Koi pending long video script nahi bacha Sheet mein!");
}
const row = inputRows[0]; // Take current pending day's row

return {
  json: {
    day: row.Day || 1,
    title: row.Title || "8 Merkkiä Siitä, Että Olet Yliälykäs (Ja Miksi Se Sattuu)",
    script: row.Script || row.Full_Script || row.Content,
    hook_top: row.Hook_Top || "8 MERKKIÄ",
    hook_highlight: row.Hook_Highlight || "OLETKO LIIAN ÄLYKÄS?",
    tags: row.Tags || "älykkyys, psykologia, yliälykkyys, mielen voima, stoalaisuus, filosofia",
    description: (row.Description || "Tilaa @Mielen_Voima saadaksesi syvällistä psykologiaa ja mielen selkeyttä viikoittain.") + "\\n\\n#mielenvoima #psykologia #älykkyys",
    sheet_row_id: row.row_number || row.ID || 1
  }
};
"""
        },
        "id": "node-prepare-payload",
        "name": "📝 Prepare Render Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-500, 400]
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://mielen-voima-long-video-engine.onrender.com/api/generate-long-video",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "X-API-Key",
                        "value": "mielen_voima_long_2026"
                    }
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": """={
  "script": {{ JSON.stringify($json.script) }},
  "title": {{ JSON.stringify($json.title) }},
  "hook_top": {{ JSON.stringify($json.hook_top) }},
  "hook_highlight": {{ JSON.stringify($json.hook_highlight) }}
}""",
            "options": {
                "timeout": 60000
            }
        },
        "id": "node-dispatch-render",
        "name": "🚀 Dispatch to Render Engine (/api/generate-long-video)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [-280, 400]
    },
    {
        "parameters": {
            "amount": 90
        },
        "id": "node-wait-initial",
        "name": "⏳ Initial Render Wait (90s)",
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [-60, 400],
        "webhookId": uid()
    },
    {
        "parameters": {
            "url": "=https://mielen-voima-long-video-engine.onrender.com/api/status/{{ $('🚀 Dispatch to Render Engine (/api/generate-long-video)').first().json.job_id }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "X-API-Key",
                        "value": "mielen_voima_long_2026"
                    }
                ]
            },
            "options": {
                "timeout": 30000
            }
        },
        "id": "node-poll-status",
        "name": "📊 Poll Render Status",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [160, 400],
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 5000,
        "continueOnFail": True
    },
    {
        "parameters": {
            "jsCode": """
const staticData = $getWorkflowStaticData('global');
staticData.pollAttempts = (staticData.pollAttempts || 0) + 1;

const MAX_POLLS = 45; // 45 x 30s = ~22 mins max buffer for 4-5 min long videos
const resp = $input.first().json;

let outcome;
if (resp.status === "completed") {
  outcome = "completed";
} else if (resp.status === "failed") {
  outcome = "failed";
} else if (staticData.pollAttempts >= MAX_POLLS) {
  outcome = "timeout";
} else {
  outcome = "retry";
}

return {
  json: {
    ...resp,
    pollAttempt: staticData.pollAttempts,
    outcome: outcome
  }
};
"""
        },
        "id": "node-eval-poll",
        "name": "🧮 Evaluate Long Render Status",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [380, 400]
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 1
                },
                "conditions": [
                    {
                        "id": "status-completed",
                        "leftValue": "={{ $json.status }}",
                        "rightValue": "completed",
                        "operator": {
                            "type": "string",
                            "operation": "equals"
                        }
                    }
                ],
                "combinator": "and"
            }
        },
        "id": "node-if-completed",
        "name": "❓ Is Long Video Render Complete?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [600, 400]
    },
    {
        "parameters": {
            "amount": 30
        },
        "id": "node-poll-wait",
        "name": "⏳ Poll Wait Loop (30s)",
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [820, 560],
        "webhookId": uid()
    },
    {
        "parameters": {
            "chatId": "1306188611",
            "text": '=❌ Mielen Voima: Long Video Render Failed!\n\n📌 Reason: {{ $json.outcome === "failed" ? "Render reported status: FAILED (" + $json.error + ")" : "Poll timeout after 45 attempts (~22 mins)" }}\nJob ID: {{ $json.job_id }}\n⏰ {{ $now.setZone("Asia/Kolkata").toFormat("HH:mm") }} IST',
            "additionalFields": {
                "appendAttribution": False
            }
        },
        "id": "node-tg-fail",
        "name": "📨 Telegram - Long Render Failed Alert",
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [820, 720],
        "credentials": {
            "telegramApi": {
                "id": "NFRtoAZzCQgOlUda",
                "name": "html to imag bot render puptr"
            }
        }
    },
    {
        "parameters": {
            "url": "=https://mielen-voima-long-video-engine.onrender.com{{ $json.download_video_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "X-API-Key",
                        "value": "mielen_voima_long_2026"
                    }
                ]
            },
            "options": {
                "response": {
                    "response": {
                        "responseFormat": "file"
                    }
                },
                "timeout": 180000
            }
        },
        "id": "node-dl-video",
        "name": "⬇️ Download 1080p MP4 Video",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [820, 260]
    },
    {
        "parameters": {
            "url": "=https://mielen-voima-long-video-engine.onrender.com{{ $('🧮 Evaluate Long Render Status').first().json.download_thumbnail_url }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "X-API-Key",
                        "value": "mielen_voima_long_2026"
                    }
                ]
            },
            "options": {
                "response": {
                    "response": {
                        "responseFormat": "file"
                    }
                },
                "timeout": 60000
            }
        },
        "id": "node-dl-thumb",
        "name": "⬇️ Download 1280x720 Thumbnail PNG",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1040, 260]
    },
    {
        "parameters": {
            "resource": "video",
            "operation": "upload",
            "title": "={{ $('📝 Prepare Render Payload').first().json.title }}",
            "regionCode": "FI",
            "categoryId": "27",
            "options": {
                "defaultLanguage": "fi",
                "description": "={{ $('📝 Prepare Render Payload').first().json.description }}",
                "notifySubscribers": True,
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "tags": "={{ $('📝 Prepare Render Payload').first().json.tags }}"
            }
        },
        "id": "node-yt-upload-video",
        "name": "🎬 Upload Long Video to YouTube",
        "type": "n8n-nodes-base.youTube",
        "typeVersion": 1,
        "position": [1260, 260],
        "credentials": {
            "youTubeOAuth2Api": {
                "id": "kr3p86tvnD15ES0g",
                "name": "finland channel power of mind"
            }
        }
    },
    {
        "parameters": {
            "method": "POST",
            "url": "=https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={{ $json.id }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "youTubeOAuth2Api",
            "sendBody": True,
            "contentType": "binaryData",
            "inputDataFieldName": "data",
            "options": {
                "timeout": 60000
            }
        },
        "id": "node-yt-upload-thumb",
        "name": "🖼️ Upload Custom Thumbnail to YouTube (OAuth)",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [1480, 260],
        "credentials": {
            "youTubeOAuth2Api": {
                "id": "kr3p86tvnD15ES0g",
                "name": "finland channel power of mind"
            }
        }
    },
    {
        "parameters": {
            "operation": "update",
            "documentId": {
                "__rl": True,
                "value": "13ZSBJQrevEo2lJqZ_LoTLyJ_6sEKjHFwhauqmHTamoc",
                "mode": "list"
            },
            "sheetName": {
                "__rl": True,
                "value": 1374005491,
                "mode": "list"
            },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "Status": "published",
                    "row_number": "={{ $('📝 Prepare Render Payload').first().json.sheet_row_id }}"
                },
                "matchingColumns": ["row_number"]
            }
        },
        "id": "node-sheet-update",
        "name": "📊 Mark Google Sheet as Published",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [1700, 260],
        "credentials": {
            "googleSheetsOAuth2Api": {
                "id": "ew6mItBZu7P6dspU",
                "name": "Google Sheets account 100 account"
            }
        }
    },
    {
        "parameters": {
            "chatId": "1306188611",
            "text": '=🎉 Mielen Voima: Daily Long Video Published!\n\n🎬 Title: {{ $(\'📝 Prepare Render Payload\').first().json.title }}\n⏱ Duration: {{ $(\'🧮 Evaluate Long Render Status\').first().json.duration_seconds }}s (~{{ Math.round($(\'🧮 Evaluate Long Render Status\').first().json.duration_seconds / 60) }} min)\n📦 Size: {{ $(\'🧮 Evaluate Long Render Status\').first().json.video_size_mb }} MB\n🔗 YouTube Link: https://youtu.be/{{ $(\'🎬 Upload Long Video to YouTube\').first().json.id }}\n\nThumbnail uploaded successfully! ✅',
            "additionalFields": {
                "appendAttribution": False
            }
        },
        "id": "node-tg-success",
        "name": "📨 Telegram - Long Video Published Alert",
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [1920, 260],
        "credentials": {
            "telegramApi": {
                "id": "NFRtoAZzCQgOlUda",
                "name": "html to imag bot render puptr"
            }
        }
    }
]

# Build connections mapping
c = {}
def connect(src, dst, src_out=0, dst_in=0, ctype='main'):
    if src not in c:
        c[src] = {ctype: []}
    while len(c[src][ctype]) <= src_out:
        c[src][ctype].append([])
    c[src][ctype][src_out].append({"node": dst, "type": ctype, "index": dst_in})

connect("⏰ Daily Schedule Trigger (19:00 FI / 21:30 IST)", "🔁 Reset Poll Counters")
connect("🔁 Reset Poll Counters", "🔔 Wake Render Engine (GET /health)")
connect("🔔 Wake Render Engine (GET /health)", "⏳ Wait for Render Spin-up (45s)")
connect("⏳ Wait for Render Spin-up (45s)", "📊 Get Today Long Video Script from Sheet")
connect("📊 Get Today Long Video Script from Sheet", "📝 Prepare Render Payload")
connect("📝 Prepare Render Payload", "🚀 Dispatch to Render Engine (/api/generate-long-video)")
connect("🚀 Dispatch to Render Engine (/api/generate-long-video)", "⏳ Initial Render Wait (90s)")
connect("⏳ Initial Render Wait (90s)", "📊 Poll Render Status")
connect("📊 Poll Render Status", "🧮 Evaluate Long Render Status")
connect("🧮 Evaluate Long Render Status", "❓ Is Long Video Render Complete?")

# If Completed (true: index 0) -> Download Video
connect("❓ Is Long Video Render Complete?", "⬇️ Download 1080p MP4 Video", src_out=0)
# If Not Completed (false: index 1) -> Poll Wait Loop
connect("❓ Is Long Video Render Complete?", "⏳ Poll Wait Loop (30s)", src_out=1)
connect("⏳ Poll Wait Loop (30s)", "📊 Poll Render Status")

# Sequential pipeline after download video
connect("⬇️ Download 1080p MP4 Video", "⬇️ Download 1280x720 Thumbnail PNG")
connect("⬇️ Download 1280x720 Thumbnail PNG", "🎬 Upload Long Video to YouTube")
connect("🎬 Upload Long Video to YouTube", "🖼️ Upload Custom Thumbnail to YouTube (OAuth)")
connect("🖼️ Upload Custom Thumbnail to YouTube (OAuth)", "📊 Mark Google Sheet as Published")
connect("📊 Mark Google Sheet as Published", "📨 Telegram - Long Video Published Alert")

workflow = {
    "name": "Mielen Voima - Daily Long Video Automation (1080p + Thumbnail)",
    "nodes": nodes,
    "connections": c,
    "active": False,
    "settings": {
        "executionOrder": "v1"
    }
}

out_path = Path(__file__).parent / "mielen_voima_long_video_workflow.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Workflow JSON generated successfully -> {out_path}")
print(f"Total Nodes: {len(nodes)}")
