import Dashboard from './Dashboard';
import Replay from './Replay';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/replay/:runId" element={<Replay />} />
      </Routes>
    </BrowserRouter>
  );
}
