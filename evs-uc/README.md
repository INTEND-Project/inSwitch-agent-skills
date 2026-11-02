# EVS use case

Set `OPENAI_API_KEY`, then build the base agent image and start both services
using the standalone Compose file:

```bash
export OPENAI_API_KEY="your_openai_api_key"
docker compose -f docker-compose.yaml build agent
docker compose -f evs-uc/docker-compose.yaml up --build
```

Run these commands from the project root. The EVS image extends
`songhui/inswitch:${TAG:-latest}` and includes kubectl and Helm. Set `TAG`
consistently for both commands if using a non-default tag. The build supports
Linux amd64 and arm64; tool versions are pinned in the Dockerfile and can be
changed with build arguments.

The agent mounts `evs-uc/workspace/` at `/workspace`, `evs-uc/logs/` at `/logs`, and
`evs-uc/credentials/` read-only at `/credentials`. The credentials directory is
ignored by Git and excluded from the image build context. Configure a kubeconfig
and any referenced credential files for their paths inside the container; for
example, set `KUBECONFIG=/credentials/config` when using a kubeconfig there.

The agent API is available at `http://localhost:8085` and the dashboard at
`http://localhost:8086`.
