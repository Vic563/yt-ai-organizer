import React from 'react';
import { Box, Container, Typography } from '@mui/material';
import PerformanceDashboard from '../components/PerformanceDashboard';

const PerformancePage = () => {
  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Container maxWidth="xl">
        <PerformanceDashboard />
      </Container>
    </Box>
  );
};

export default PerformancePage;
