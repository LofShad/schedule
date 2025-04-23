import React from 'react';
import { Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import { AppBar, Toolbar, Typography, Button } from '@mui/material';

function App() {
  const navigate = useNavigate();

  return (
    <div>
      {/* Верхняя панель навигации */}
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Расписание
          </Typography>
          {/* Кнопки для перехода на разные страницы */}
          <Button color="inherit" onClick={() => navigate('/subjects')}>Предметы</Button>
          <Button color="inherit" onClick={() => navigate('/teachers')}>Учителя</Button>
          <Button color="inherit" onClick={() => navigate('/classes')}>Классы</Button>
          <Button color="inherit" onClick={() => navigate('/plans')}>Учебные планы</Button>
          <Button color="inherit" onClick={() => navigate('/days-off')}>Выходные</Button>
          <Button color="inherit" onClick={() => navigate('/schedule')}>Расписание</Button>
        </Toolbar>
      </AppBar>

      {/* Маршруты */}
      <Routes>
        <Route path="/" element={<Navigate to="/subjects" />} />
        <Route path="/subjects" element={<div>Предметы</div>} />
        <Route path="/teachers" element={<div>Учителя</div>} />
        <Route path="/classes" element={<div>Классы</div>} />
        <Route path="/plans" element={<div>Планы</div>} />
        <Route path="/days-off" element={<div>Выходные</div>} />
        <Route path="/schedule" element={<div>Расписание</div>} />
      </Routes>
    </div>
  );
}

export default App;
