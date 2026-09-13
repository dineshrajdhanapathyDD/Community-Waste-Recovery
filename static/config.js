// ---------------------------------------------------------------------------
// Frontend configuration for the Good Neighbor Agent SPA.
//
// This is a TEMPLATE / local placeholder. During a real deploy,
// static/AgentCode/launchAgent.sh regenerates this file with the live values
// pulled from the `bootstrap-stack` CloudFormation outputs and the deployed
// AgentCore runtime, then uploads it to the S3 bucket behind CloudFront.
//
// The SPA reads window.WORKSHOP_CONFIG at load time. If the values below are
// still the "YOUR_..." placeholders, the app runs in DEMO MODE (mocked agent
// replies) so you can see the UI without any AWS resources.
// ---------------------------------------------------------------------------
window.WORKSHOP_CONFIG = {
    COGNITO_USER_POOL_ID: 'YOUR_USER_POOL_ID',
    COGNITO_CLIENT_ID: 'YOUR_CLIENT_ID',
    S3_BUCKET_NAME: 'YOUR_S3_BUCKET_NAME',
    COGNITO_REGION: 'us-east-1',
    AGENTCORE_RUNTIME_ARN: 'YOUR_AGENTCORE_RUNTIME_ARN',
    AGENTCORE_ENDPOINT: 'https://bedrock-agentcore.us-east-1.amazonaws.com',

    // Optional: the deployed backend tools API (SAM stack good-neighbor-backend).
    // When set, the SPA answers from this real data even without the full
    // AgentCore runtime — useful to show the backend working end to end.
    BACKEND_API_URL: 'https://h1aly0x3a1.execute-api.us-east-1.amazonaws.com',
};
