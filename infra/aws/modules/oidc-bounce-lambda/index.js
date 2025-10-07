// This lambda is solely needed for the dynamic deployment of SPAR dev
// instances. It allows us to use the same static callback on the OIDC side
// (Google OIDC) without needing to update it whenever a new instance comes up

exports.handler = async (event) => {
  // Parse returnTo from state QSP
  const { queryStringParameters } = event;
  const { returnTo } = JSON.parse(Buffer.from(queryStringParameters.state, 'base64').toString('utf-8'));
  const returnToUrl = new URL(returnTo);

  // Pass QSP to return URL
  for (const [key, value] of Object.entries(queryStringParameters)) {
    returnToUrl.searchParams.set(key, value);
  }

  return {
    // Redirect to return URL (incl. QSP)
    statusCode: 302,
    headers: {
      Location: returnToUrl.href,
    },
  };
};
