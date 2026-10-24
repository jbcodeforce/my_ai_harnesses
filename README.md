# My AI Agents

This repository includes a set of agents doing focused actvities on local workspace or file systems. The first agents built is to do some work into a MyAIAssistant workspace.

## Pre-requisites

* uv
* virtual environment under:
* ./start_omlx.sh
* Set environment variables in an .env file, and reference this file with ML_ENV_FILE.
    ```sh
    # Under project folder
    export ML_ENV_FILE=$PWD/.env
    ```

The .env has the following env variables:
```sh
LLM_BASE_URL=
LLM_MODEL=
LLM_TEMPERATURE=0.4
LLM_API_KEY=local-key
EMBEDDER_MODEL=bge-small-en-v1.5-8bit
EMBEDDER_BASE_URL=http://10.0.0.148:7999/v1
```


## When to use them

## How to run

* Run the database review agent
    ```sh
    uv run db_review_agent --w <workpace_folder> --dburl <URL> | -sqllitefile <path> 
    ```

## One Agno OS Server

```sh
```

If the agent_os runs, on http://localhost:7777, use [os.agno.com](https://os.agno.com) to add a new connection to the local agent, then use chat to interact with the agent.