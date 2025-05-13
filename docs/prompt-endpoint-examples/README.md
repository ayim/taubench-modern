# Demo TypeScript Client for Prompt Endpoint Streaming

This is a demo TypeScript client for streaming responses from the Prompt Endpoint.

Run `npm i` to install the dependencies. Make sure to set the `OPENAI_API_KEY` environment variable to a valid OpenAI API key.

Usage (images):

```bash
tsx stream-multi-modal.ts -t "What's on this whiteboard; dont make stuff up, just relay the text" -i ex-whiteboard.jpg -m o4-mini-high
```

Example output:

```json
{
  "role": "agent",
  "content": [
    {
      "kind": "text",
      "text": "Here’s a faithful transcription of every bit of text I can read on the board, grouped roughly by its shape and position in the flow:\n\n1. Rectangle (start)  \n   “Distribute forms to student”\n\n2. Rectangle  \n   “Fill out forms”\n\n3. Rectangle  \n   “Validate forms”\n\n4. Diamond  \n   “Valid?”\n\n   – No → loops back to “Fill out forms”  \n   – Yes → proceeds to “Inform Applicant”\n\n5. Rectangle (to the right of “Valid?”)  \n   “Inform Applicant”\n\n6. Diamond  \n   “Eligible Applicant?”\n\n   – No → goes to a rectangle containing just “?”  \n   – Yes → goes to “Create Student Record”\n\n7. Diamond (below “Validate forms,” feeding into the same “Create Student Record” path)  \n   “Student Exists?”\n\n   – Yes → arrow up/right into “Create Student Record”  \n   – No → goes down to “Security Risk?”\n\n8. Diamond  \n   “Security Risk?”\n\n   – Yes → goes to rectangle “Deal with it”  \n   – No → goes to the same “?” rectangle mentioned above\n\n9. Rectangle (that “?” feeds into the rest of the process once resolved)  \n   “?”\n\n10. Rectangle  \n    “Create Student Record”\n\n11. Rectangle  \n    “Enroll in Seminars”\n\n12. Rectangle  \n    “Calculate Fees”\n\n13. Rectangle  \n    “Request Payment”\n\n14. Diamond  \n    “Sufficient Funds?”\n\n    – No → (back to “Request Payment”?)  \n    – Yes → goes to “Collect Fees”\n\n15. Rectangle  \n    “Collect Fees”\n\n16. Rectangle  \n    “Produce Receipt”\n\nThat’s all of the text as it appears, including the decision diamonds, process boxes, loops and the lone “?” box."
    }
  ],
  "additional_response_fields": {
    "id": "chatcmpl-BWWcbvi6CZOUjeYlN9sj8bExd0qXi",
    "model": "o4-mini-2025-04-16"
  },
  "stop_reason": "stop",
  "metadata": {
    "sema4ai_metadata": {
      "platform_name": "openai"
    }
  }
}

```

Usage (audio):

```bash
tsx stream-multi-modal.ts -t "Transcribe this audio" -a ex-audio.mp3 -m gpt-4o-audio
```

**Important:** You _must_ use the `gpt-4o-audio` model to stream audio.

Example output:

```json
{
  "role": "agent",
  "content": [
    {
      "kind": "text",
      "text": "So we decided we had to put in a new well, and somebody asked me why I didn't get it witched. And I didn't know what he was talking about. So they said there's an old fella out here that witches wells, and he'll get you water every time. So I said, okay, how much does he want? He wants ten bucks. I said, bring him on. So we brought this fella out, and he went through his maneuvers with this peach stick, or, I don't remember now if it was a peach stick or a willow. \n\nNew user: \"You used both, though.\"\n\nYeah, either one. One works as good as the other. And he strikes a point where he has a, where he hits water. And he puts a stone down. Then he goes down, uh, in that same line, and where he hits water again, put another stone down. Then he goes at right angles with this, and gets a stone over here, and a stone over here, and where these two lines cross, that's the point.\n\nNew user: \"Kind of be, uh, the kind of...\"\n\nThe veins, the, he said these water veins always run on an angle. Never do north and south or east and west. They're northwest-southeast."
    }
  ],
  "additional_response_fields": {
    "id": "chatcmpl-BWWk5HUEjFQoQqsiif297e1cYkc24",
    "model": "gpt-4o-audio-preview-2024-12-17"
  },
  "stop_reason": "stop",
  "metadata": {
    "sema4ai_metadata": {
      "platform_name": "openai"
    }
  }
}
```

This will stream the response JSON to the console as it's constructed.

Usage (PDF|Reducto):

```bash
tsx stream-multi-modal.ts -t "Extract all the text accurately." --pdf ./ex-invoice.pdf -m reducto-standard-parse
```

Example output:

```json
{
  "content": [
    {
      "kind": "text",
      "text": "INVOICE 0012820"
    },
    {
      "kind": "text",
      "text": "Date: 27.08.2019"
    },
    {
      "kind": "text",
      "text": "ConIncorporated\n\n305 Fleet Rd\nFleet, Hampshire County,\nGU51 3BU\n012 5261 2116\nadmin@conincorp.co.uk"
    },
    {
      "kind": "text",
      "text": "SHIP TO:"
    },
    {
      "kind": "text",
      "text": "Caitlin Roberts\n\nAwthentikz\n\n89 Annfield Rd\n\nBEARLEY, CV37 7GQ\n079 0608 3650\n\nCustomer ID: CN0044"
    },
    {
      "kind": "text",
      "text": "BILL TO:"
    },
    {
      "kind": "text",
      "text": "Caitlin Roberts\nAwthentikz\n89 Annfield Rd\n\nBEARLEY, CV37 7GQ\n079 0608 3650\nCustomer ID: CN0044"
    },
    {
      "kind": "text",
      "text": "<table><tr><th>ORDER DATE</th><th>ORDER NUMBER</th><th>DUE DATE</th></tr><tr><td>27.08.2019</td><td>PO-001522</td><td>27.09.2019</td></tr></table>"
    },
    {
      "kind": "text",
      "text": "<table><tr><th>Item #</th><th>Ordered Service</th><th>Item Price</th><th>Total</th></tr><tr><td>1</td><td>10-700 - Exterior Protection (10)</td><td>40.29</td><td>402.9</td></tr><tr><td>2</td><td>1-515 - Temporary Lighting (29)</td><td>93.55</td><td>2712.95</td></tr><tr><td>3</td><td>11-060 - Theater and Stage Equipment (17)</td><td>78.83</td><td>1340.11</td></tr><tr><td>4</td><td>1-600 - Product Requirements (Scope of Work) (20)</td><td>13.72</td><td>274.4</td></tr><tr><td>5</td><td>12-050 - Fabrics (23)</td><td>94.48</td><td>2173.04</td></tr><tr><td>6</td><td>2-823 - PVC Fences and Gates (27)</td><td>23.76</td><td>641.52</td></tr><tr><td>7</td><td>6-400 - Architectural Woodwork (26)</td><td>8.86</td><td>230.36</td></tr><tr><td>8</td><td>2-820 - Fences and Gates (15)</td><td>99.91</td><td>1498.65</td></tr><tr><td>9</td><td>9-700 - Wall Finishes (1)</td><td>27.31</td><td>27.31</td></tr><tr><td>10</td><td>2-795 - Porous Paving (30)</td><td>36.44</td><td>1093.2</td></tr><tr><td>11</td><td>11 - Equipment (9)</td><td>50.34</td><td>453.06</td></tr><tr><td>12</td><td>5-050 - Basic Metal Materials and Methods (16)</td><td>94.24</td><td>1507.84</td></tr><tr><td>13</td><td>15-600 - Refrigeration Equipment (29)</td><td>96.99</td><td>2812.71</td></tr><tr><td>14</td><td>10-800 - Toilet, Bath, and Laundry Specialties (23)</td><td>2.75</td><td>63.25</td></tr><tr><td>15</td><td>13-200 - Storage Tanks (25)</td><td>99.25</td><td>2481.25</td></tr></table>"
    },
    {
      "kind": "text",
      "text": "Please contact Customer Service at Phone with any questions or comments. THANK YOU FOR YOUR BUSINESS!"
    }
  ],
  "role": "agent",
  "stop_reason": null,
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  },
  "metrics": {},
  "metadata": {
    "reducto_blocks": [
      {
        "reducto_block_confidence": "high",
        "reducto_block_type": "Title",
        "reducto_block_bbox": {
          "height": 0.029671717171717172,
          "left": 0.12336601307189543,
          "page": 1,
          "top": 0.10037878787878787,
          "width": 0.37336601307189543,
          "original_page": 1
        },
        "reducto_block_image_url": null
      },
      {
        "reducto_block_confidence": "high",
        "reducto_block_type": "Header",
        "reducto_block_bbox": {
          "height": 0.007575757575757576,
          "left": 0.7622549019607843,
          "page": 1,
          "top": 0.09217171717171717,
          "width": 0.10784313725490197,
          "original_page": 1
        },
        "reducto_block_image_url": null
      },
      // ...,
    ],
    "reducto_chunks": {
      "reducto_chunk_enrichment_success": false,
      "chunk_embed_text": "# INVOICE 0012820\n\nConIncorporated\n\n305 Fleet Rd\nFleet, Hampshire County,\nGU51 3BU\n012 5261 2116\nadmin@conincorp.co.uk\n\nSHIP TO:\n\nCaitlin Roberts\n\nAwthentikz\n\n89 Annfield Rd\n\nBEARLEY, CV37 7GQ\n079 0608 3650\n\nCustomer ID: CN0044\n\nBILL TO:\n\nCaitlin Roberts\nAwthentikz\n89 Annfield Rd\n\nBEARLEY, CV37 7GQ\n079 0608 3650\nCustomer ID: CN0044\n\nThis table presents details of a specific order, indicating that the order was placed on August 27, 2019, under the order number PO-001522. The due date for this order is set for September 27, 2019.\n\nThis table presents a detailed breakdown of various ordered services, including the item number, description, item price, and total cost for each service. The prices range from $2.75 to $96.99, with total costs varying significantly depending on the service ordered, leading to overall totals from $27.31 to $2812.71. The aggregate values reflect a diverse selection of services, notably in areas such as exterior protection, temporary lighting, and refrigeration equipment.\n\nPlease contact Customer Service at Phone with any questions or comments. THANK YOU FOR YOUR BUSINESS!"
    },
    "reducto_duration": 5.882708311080933,
    "reducto_job_id": "8bf35cac-114f-406c-b9d1-3d851d91af90",
    "reducto_pdf_url": "https://reducto-ai-storage20250512184122375800000007.s3.amazonaws.com/...",
    "reducto_usage": {
      "num_pages": 1
    }
  },
  "additional_response_fields": {}
}
```

**PDF Notes:**

- You'll need to set a REDUCTO_API_KEY environment variable to use the `reducto-standard-parse` model.
- The `reducto-standard-parse` model is very experimental and not all features are available.
- There's a `reducto-standard-extract` model that is NOT ready yet, but in the future will be able to extract structured data into a specific schema (provided as part of your prompt).
- There's no real "streaming" for Reducto, you can hit the stream endpoint but the content will only return after it's finished processing.
