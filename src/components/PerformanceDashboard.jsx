import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Grid, 
  Tabs, 
  Tab, 
  Paper, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  CircularProgress, 
  Alert, 
  MenuItem, 
  Select, 
  FormControl, 
  InputLabel, 
  Typography,
  Container,
  CardHeader,
  IconButton,
  Tooltip,
  Button
} from '@mui/material';
import SpeedIcon from '@mui/icons-material/Speed';
import TimerIcon from '@mui/icons-material/Timer';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import api from '../services/api';

// Time Range Selector Component
const TimeRangeSelector = ({ timeRange, setTimeRange }) => {
  // Style for white text in TimeRangeSelector
  const whiteTextStyle = { color: 'common.white', '&.Mui-focused': { color: 'common.white' } };
  const whiteIconStyle = { color: 'common.white' };

  return (
    <FormControl size="small" sx={{ minWidth: 150 }}>
      <InputLabel id="time-range-label" sx={whiteTextStyle}>Time Range</InputLabel>
      <Select
        labelId="time-range-label"
        value={timeRange}
        label="Time Range"
        onChange={(e) => setTimeRange(e.target.value)}
        sx={{ 
          color: 'common.white', 
          '.MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255, 255, 255, 0.5)' },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'common.white' },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'common.white' },
          '.MuiSvgIcon-root': whiteIconStyle 
        }}
      >
        <MenuItem value={1}>Last Hour</MenuItem>
        <MenuItem value={6}>Last 6 Hours</MenuItem>
        <MenuItem value={24}>Last 24 Hours</MenuItem>
        <MenuItem value={72}>Last 3 Days</MenuItem>
        <MenuItem value={168}>Last Week</MenuItem>
      </Select>
    </FormControl>
  );
};

// Metrics Card Component
const MetricsCard = ({ title, value, icon, color, subtitle }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Grid container spacing={2} alignItems="center">
        <Grid item>
          <Box
            sx={{
              backgroundColor: `${color}.light`,
              borderRadius: '50%',
              p: 1,
              display: 'flex',
              color: `${color}.dark`
            }}
          >
            {icon}
          </Box>
        </Grid>
        <Grid item xs>
          <Typography variant="h6" component="div" color="text.secondary">
            {title}
          </Typography>
          <Typography variant="h4" component="div" sx={{ fontWeight: 'bold' }}>
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        </Grid>
      </Grid>
    </CardContent>
  </Card>
);

const PerformanceDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState(24);
  const [tabValue, setTabValue] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [openResetDialog, setOpenResetDialog] = useState(false);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const [metricsRes, slowEndpointsRes] = await Promise.all([
        api.get(`/performance/metrics?hours=${timeRange}`),
        api.get(`/performance/slow-endpoints?hours=${timeRange}`)
      ]);
      
      setMetrics({
        ...metricsRes.data,
        slowEndpoints: slowEndpointsRes.data || []
      });
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      console.error('Error fetching performance metrics:', err);
      setError('Failed to load performance data. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [timeRange]);

  const handleRefresh = () => {
    fetchMetrics();
  };

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleOpenResetDialog = () => {
    setOpenResetDialog(true);
  };

  const handleCloseResetDialog = () => {
    setOpenResetDialog(false);
  };

  const handleConfirmReset = async () => {
    try {
      setLoading(true);
      await api.delete('/performance/reset-metrics');
      await fetchMetrics(); // Refresh metrics after reset
      setOpenResetDialog(false);
      // Optionally, show a success notification here
    } catch (err) {
      console.error('Error resetting performance metrics:', err);
      setError('Failed to reset performance data. Please try again.');
      // Optionally, show an error notification here
      setOpenResetDialog(false);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !metrics) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={3}>
        <Paper elevation={3} sx={{ p: 3, textAlign: 'center' }}>
          <Typography color="error">{error}</Typography>
          <Button 
            variant="outlined" 
            onClick={fetchMetrics}
            startIcon={<RefreshIcon />}
            sx={{ mt: 2 }}
          >
            Retry
          </Button>
        </Paper>
      </Box>
    );
  }

  if (!metrics || !metrics.endpoints || metrics.endpoints.length === 0) {
    return (
      <Box p={3}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h4" component="h1">
            Performance Dashboard
          </Typography>
          <TimeRangeSelector timeRange={timeRange} setTimeRange={setTimeRange} />
        </Box>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            No performance data available
          </Typography>
          <Typography color="textSecondary" paragraph>
            Use the application to generate performance metrics.
          </Typography>
          <Button 
            variant="contained" 
            onClick={fetchMetrics}
            startIcon={<RefreshIcon />}
          >
            Refresh
          </Button>
        </Paper>
      </Box>
    );
  }

  // Prepare endpoint data for tables
  const endpointStats = metrics.endpoints.map(ep => ({
    method: ep.method || 'UNKNOWN',
    path: ep.path || '/unknown',
    avgResponseTime: ep.avg_response_time ? `${ep.avg_response_time.toFixed(2)}ms` : 'N/A',
    requestCount: ep.request_count || 0,
    errorRate: ep.request_count > 0 
      ? `${((ep.error_count || 0) / ep.request_count * 100).toFixed(2)}%` 
      : '0%',
    lastCalled: ep.last_called ? new Date(ep.last_called).toLocaleString() : 'Never'
  }));

  // Sort slow endpoints by response time
  const slowEndpoints = [...(metrics.slowEndpoints || [])].sort((a, b) => 
    (b.avg_response_time || 0) - (a.avg_response_time || 0)
  ).map(ep => ({
    method: ep.method || 'UNKNOWN',
    path: ep.path || '/unknown',
    responseTime: ep.avg_response_time ? `${ep.avg_response_time.toFixed(2)}ms` : 'N/A',
    p90: ep.p90 ? `${ep.p90.toFixed(2)}ms` : 'N/A',
    p99: ep.p99 ? `${ep.p99.toFixed(2)}ms` : 'N/A'
  }));

  // Calculate summary metrics
  const totalRequests = endpointStats.reduce((sum, ep) => sum + (ep.requestCount || 0), 0);
  const errorRate = totalRequests > 0 
    ? (endpointStats.reduce((sum, ep) => sum + (parseFloat(ep.errorRate) || 0), 0) / endpointStats.length).toFixed(2) + '%'
    : '0%';
  const avgResponseTime = endpointStats.length > 0
    ? (endpointStats.reduce((sum, ep) => {
        const time = parseFloat(ep.avgResponseTime) || 0;
        return sum + time;
      }, 0) / endpointStats.length).toFixed(2) + 'ms'
    : 'N/A';

  return (
    <Box p={3}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom sx={{ color: 'common.white' }}>
            Performance Dashboard
          </Typography>
          <Typography variant="body2" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            Last updated: {lastUpdated.toLocaleString()}
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <TimeRangeSelector timeRange={timeRange} setTimeRange={setTimeRange} />
          <Tooltip title="Refresh data">
            <IconButton onClick={handleRefresh} sx={{ color: 'common.white' }} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Reset all metrics">
            <IconButton onClick={handleOpenResetDialog} sx={{ color: 'common.white' }} disabled={loading}>
              <DeleteSweepIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <MetricsCard
            title="Total Requests"
            value={totalRequests.toLocaleString()}
            icon={<SpeedIcon />}
            color="info"
            subtitle={`in last ${timeRange} hour${timeRange !== 1 ? 's' : ''}`}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <MetricsCard
            title="Avg. Response Time"
            value={avgResponseTime}
            icon={<TimerIcon />}
            color="success"
            subtitle="across all endpoints"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <MetricsCard
            title="Error Rate"
            value={errorRate}
            icon={<ErrorIcon />}
            color="error"
            subtitle="of all requests"
          />
        </Grid>
      </Grid>

      <Paper sx={{ p: 3, mb: 4 }}>
        <Tabs value={tabValue} onChange={handleTabChange} sx={{ mb: 3 }}>
          <Tab label="Endpoint Statistics" />
          <Tab label="Slow Endpoints" />
        </Tabs>
        
        {tabValue === 0 && (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Endpoint</TableCell>
                  <TableCell align="right">Avg. Response Time</TableCell>
                  <TableCell align="right">Request Count</TableCell>
                  <TableCell align="right">Error Rate</TableCell>
                  <TableCell>Last Called</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {endpointStats.map((ep, index) => (
                  <TableRow key={index} hover>
                    <TableCell>
                      <Box>
                        <Typography variant="subtitle2">{ep.method} {ep.path}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">{ep.avgResponseTime}</TableCell>
                    <TableCell align="right">{ep.requestCount.toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <Box display="flex" alignItems="center" justifyContent="flex-end">
                        {parseFloat(ep.errorRate) > 10 ? (
                          <ErrorIcon color="error" sx={{ fontSize: 16, mr: 0.5 }} />
                        ) : parseFloat(ep.errorRate) > 0 ? (
                          <WarningIcon color="warning" sx={{ fontSize: 16, mr: 0.5 }} />
                        ) : (
                          <CheckCircleIcon color="success" sx={{ fontSize: 16, mr: 0.5 }} />
                        )}
                        {ep.errorRate}
                      </Box>
                    </TableCell>
                    <TableCell>{ep.lastCalled}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {tabValue === 1 && (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Endpoint</TableCell>
                  <TableCell align="right">Avg. Response Time</TableCell>
                  <TableCell align="right">P90</TableCell>
                  <TableCell align="right">P99</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {slowEndpoints.map((ep, index) => (
                  <TableRow key={index} hover>
                    <TableCell>
                      <Box>
                        <Typography variant="subtitle2">{ep.method} {ep.path}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">{ep.responseTime}</TableCell>
                    <TableCell align="right">{ep.p90}</TableCell>
                    <TableCell align="right">{ep.p99}</TableCell>
                  </TableRow>
                ))}
                {slowEndpoints.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                      <Box>
                        <SpeedIcon color="action" sx={{ fontSize: 40, mb: 1 }} />
                        <Typography variant="subtitle1" color="textSecondary">
                          No slow endpoints detected
                        </Typography>
                        <Typography variant="body2" color="textSecondary">
                          All endpoints are performing within expected thresholds
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <ResetConfirmationDialog 
        open={openResetDialog} 
        handleClose={handleCloseResetDialog} 
        handleConfirm={handleConfirmReset} 
      />
    </Box>
  );
};

export default PerformanceDashboard;

// Helper for Dialog (can be part of the component or separate)
const ResetConfirmationDialog = ({ open, handleClose, handleConfirm }) => (
  <Dialog
    open={open}
    onClose={handleClose}
    aria-labelledby="alert-dialog-title"
    aria-describedby="alert-dialog-description"
  >
    <DialogTitle id="alert-dialog-title">
      {"Reset Performance Metrics?"}
    </DialogTitle>
    <DialogContent>
      <DialogContentText id="alert-dialog-description">
        Are you sure you want to reset all performance metrics? This action cannot be undone.
      </DialogContentText>
    </DialogContent>
    <DialogActions>
      <Button onClick={handleClose}>Cancel</Button>
      <Button onClick={handleConfirm} color="error" autoFocus>
        Reset
      </Button>
    </DialogActions>
  </Dialog>
);
