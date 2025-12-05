# Guide to Generative AI Usage Patterns in Agent Server For Google Platform

For a long time, Google maintained two completely separate "stacks" for generative AI: **Vertex AI** for Enterprise and **Google AI Studio** for quick prototyping. In mid-2025, Google merged the two into a single SDK. This has led to gaps in Google's own documentation, where there are omissions and code examples that don't run as directed. There are also accomodations built into the google SDK that handle the vertex/ai-studio merge that we have to work around, for example, to automatically prefer AI-Studio over Vertex when an API key is stored in the client config.

#### This guide provides two things:

- 1. A guide for _users_ to set permissions correctly for users to connect their Google accounts to Google models using Sema4's agent-platform.
- 2. A guide for _developers_ to identify where the Google Platform converntions differ from other AI platforms in agent-server.

AI Studio works more similarly to OpenAI: you just need an API key and you have access. Vertex puts the onus on the user to configure their account correctly, requiring a service level account with specific IAM provisions and roles. This may lead to issues for customers in the future. Sema4 needs Vertex because some customers require enterprise controls (like data residency). AI Studio is included for those users who don't want to set up an enterprise account.

## USER GUIDE

#### Using AI Studio (12/01/25)

All you need is an API key. Go to [Google AI Studio](aistudio.google.com) and create one from there. When configuring the LLM with Google as a platform, ensure "Use Google Vertex" is _deselected_ (this is the default).

Note:

- **You will not be able to use Gemini 3 Pro Preview with an AI Studio configuration.** The reason is that gemini 3 pro can only be used in "express mode" as of this writing, and Sema4 can't support this feature at this time.
- When editing an LLM configuration in Sema4 to change from AI Studio to Vertex (or the reverse), you may run into errors where agents will not load because models are enabled differently between Vertex and Google AI Studio, and the two accounts may not match each other's model permissions.
- Your usage rates will default to fairly low levels on a free tier. Upgrade to a billing plan to increase them.
- If you include an API Key, Google's SDK will default to initializing your LLM client with AI Studio. **_If you save an LLM with a Google API Key, that LLM can only be used with AI Studio from then on. You cannot edit that LLM to use Vertex. You must create a new LLM config._**

#### Using Vertex (12/01/25)

You will first need to create a Google _Service Account_ for authentication.

#### How to Get a Service Account

1.  **Create a Google Cloud Project:** If you don't have one, make one at [Google Cloud Console](https://console.cloud.google.com/).
2.  **Navigate to Service Accounts:** In the Google Cloud Console, go to **IAM & Admin** > **Service Accounts**.
3.  **Create a New Service Account:** Click **+ Create Service Account**, provide a name, and click **CREATE AND CONTINUE**.
4.  **Set IAM Roles:** In the "Grant this service account access to project" step, you assign the necessary roles (see next section).
5.  **Create Key:** After creating the account, click on it, go to the **Keys** tab, click **ADD KEY** > **Create new key**, and choose **JSON**. This JSON file is your private key credential and must be stored securely. You will also have the option to create a **P12** key, but this is not supported on Sema4. You must choose **JSON**.

#### Required IAM Roles

You need two IAM roles assigned to your service account to have permissions enabled for Sema4 Agents to work with Google Cloud.

1. AI Platform Developer - this provides full access to Google "AI Platform" resources.
2. Vertex AI User - this grants access to all resources in Vertex AI.

#### Project ID

You will need to use the same **Project ID** assigned with the above IAM roles when configuring your Sema4 LLM. The format should look similar to `my-enterprise-project-12345`. This string will also be recorded in the JSON key saved in step 5 in the Service Account section.

#### Location

Currently, Gemini 3 Pro is only supported for a `global` location. Gemini 2.5 pro and Gemini 2.5 Flash can be set to more specific locations and data regions. You can find the full list [here](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations)

Gemini 2.5 **MUST** be set to a location where it is provisioned. **_IT IS NOT PROVISIONED FOR `GLOBAL`._** This will cause the configuration to fail.

## Developer Guide

#### .env

Set `GOOGLE_USE_VERTEX_AI=True`.
Set `GOOGLE_VERTEX_SERVICE_ACCOUNT_JSON` to your JSON Service Account credential key filepath.

#### Gemini / Vertex / Studio Divergence

- Google’s client toggles between API-key and Vertex auth, injects custom httpx transport, and maps HTTP status codes into PlatformErrors
- Google annotates the streaming message metadata with caught exceptions and token metrics to keep downstream consumers backward-compatible
