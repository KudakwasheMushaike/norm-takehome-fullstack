'use client';

import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  Container,
  Divider,
  Heading,
  Input,
  Spinner,
  Stack,
  Text,
} from '@chakra-ui/react';
import { useMemo, useState } from 'react';
import HeaderNav from '@/components/HeaderNav';

type Citation = {
  source: string;
  text: string;
};

type QueryResponse = {
  query: string;
  response: string;
  citations: Citation[];
};

export default function Page() {
  const [query, setQuery] = useState('What happens if I steal from a sept?');
  const [data, setData] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
    []
  );

  async function runQuery() {
    const trimmed = query.trim();
    if (!trimmed) {
      setError('Please enter a question.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const url = `${apiBaseUrl}/query?query=${encodeURIComponent(trimmed)}`;
      const response = await fetch(url, { method: 'GET' });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail = payload?.detail || `Request failed with status ${response.status}`;
        throw new Error(detail);
      }

      const payload = (await response.json()) as QueryResponse;
      setData(payload);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box minH="100vh" bg="#F4F6FA">
      <HeaderNav signOut={() => {}} />

      <Container maxW="4xl" py={10}>
        <Stack spacing={6}>
          <Box>
            <Heading size="lg" color="#101828">
              Westeros Laws Assistant
            </Heading>
            <Text mt={2} color="#475467">
              Ask a question in natural language and review grounded citations.
            </Text>
          </Box>

          <Card bg="white" border="1px solid #E4E7EC">
            <CardBody>
              <Stack spacing={4}>
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask about laws..."
                  size="lg"
                  bg="white"
                />
                <Button
                  onClick={runQuery}
                  isDisabled={loading}
                  bg="#22356F"
                  color="white"
                  _hover={{ bg: '#1A2A59' }}
                  alignSelf="flex-start"
                >
                  {loading ? (
                    <Stack direction="row" alignItems="center">
                      <Spinner size="sm" />
                      <Text>Running query...</Text>
                    </Stack>
                  ) : (
                    'Run Query'
                  )}
                </Button>
              </Stack>
            </CardBody>
          </Card>

          {error && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              {error}
            </Alert>
          )}

          {data && (
            <Stack spacing={4}>
              <Card bg="white" border="1px solid #E4E7EC">
                <CardBody>
                  <Stack spacing={3}>
                    <Text fontSize="sm" color="#667085">
                      Query
                    </Text>
                    <Text fontWeight="semibold">{data.query}</Text>
                    <Divider />
                    <Text fontSize="sm" color="#667085">
                      Response
                    </Text>
                    <Text whiteSpace="pre-wrap">{data.response}</Text>
                  </Stack>
                </CardBody>
              </Card>

              <Heading size="md" color="#101828">
                Citations
              </Heading>
              <Stack spacing={3}>
                {data.citations.length === 0 ? (
                  <Text color="#667085">No citations returned.</Text>
                ) : (
                  data.citations.map((citation, idx) => (
                    <Card key={`${citation.source}-${idx}`} bg="white" border="1px solid #E4E7EC">
                      <CardBody>
                        <Stack spacing={2}>
                          <Text fontSize="sm" color="#667085">
                            {citation.source}
                          </Text>
                          <Text>{citation.text}</Text>
                        </Stack>
                      </CardBody>
                    </Card>
                  ))
                )}
              </Stack>
            </Stack>
          )}
        </Stack>
      </Container>
    </Box>
  );
}
