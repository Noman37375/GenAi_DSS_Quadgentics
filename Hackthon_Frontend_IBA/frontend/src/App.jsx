import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Play, RotateCcw, Volume2 } from 'lucide-react';
import { Button } from './components/button';
import './App.css';

const characterImages = {
  saleem: "img4.png",
  raza: "img10.png",
  ahmed: "img3.png",
  jameel: "img9.png"
};

const sceneBackgrounds = {
  main: "img12.png",
  alternate: "img5.png"
};

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const characterColors = {
  saleem:  { bg: "from-amber-500 to-orange-600", text: "text-amber-900", bubble: "bg-amber-50 border-amber-300" },
  ahmed: { bg: "from-blue-600 to-indigo-700", text: "text-blue-900", bubble: "bg-blue-50 border-blue-300" },
  raza: { bg: "from-slate-500 to-slate-700", text: "text-slate-900", bubble: "bg-slate-50 border-slate-300" },
  jameel: { bg: "from-emerald-500 to-teal-600", text: "text-emerald-900", bubble: "bg-emerald-50 border-emerald-300" }
};



const characterNames = {
  saleem: "Saleem (Rickshaw Driver)",
  ahmed: "Ahmed Malik (BMW Driver)",
  raza: "Constable Raza",
  jameel: "Uncle Jameel (Tea Vendor)"
};

export default function Home() {
  const [storyData, setStoryData] = useState(null);
  const [currentTurn, setCurrentTurn] = useState(-1); // -1 for intro
  const [showDialogue, setShowDialogue] = useState(false);
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [runError, setRunError] = useState(null);

  const totalTurns = storyData?.turns?.length ?? 0;

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/story`, { signal: controller.signal });
        if (res.ok) {
          const data = await res.json();
          if (data?.turns?.length) {
            setStoryData(data);
            setCurrentTurn(-1);
          }
        }
      } catch (_) {}
    })();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (currentTurn >= 0) {
      const timer = setTimeout(() => setShowDialogue(true), 500);
      return () => clearTimeout(timer);
    }
  }, [currentTurn]);

  useEffect(() => {
    let interval;
    if (isAutoPlaying && currentTurn < totalTurns - 1) {
      interval = setInterval(() => {
        setShowDialogue(false);
        setTimeout(() => {
          setCurrentTurn(prev => prev + 1);
        }, 300);
      }, 8000);
    } else if (currentTurn >= totalTurns - 1) {
      setIsAutoPlaying(false);
    }
    return () => clearInterval(interval);
  }, [isAutoPlaying, currentTurn, totalTurns]);

  const startStory = () => {
    setIsLoading(true);
    setRunError(null);
    const url = `${API_BASE}/api/run/stream`;
    const es = new EventSource(url);
    let story = { title: null, scenario: null, turns: [], conclusion: "" };
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "meta") {
          story = { title: data.title, scenario: data.scenario, turns: [], conclusion: "" };
          setStoryData({ ...story });
        } else if (data.type === "turns" && Array.isArray(data.newTurns)) {
          const prevLen = story.turns.length;
          story.turns = [...story.turns, ...data.newTurns];
          setStoryData({ ...story });
          setCurrentTurn((prev) => (prev === prevLen - 1 && prev >= 0 ? story.turns.length - 1 : prev));
        } else if (data.type === "conclusion") {
          story.conclusion = data.conclusion ?? "";
          setStoryData({ ...story });
        } else if (data.type === "done") {
          es.close();
          setCurrentTurn(-1);
          setIsLoading(false);
        }
      } catch (_) {}
    };
    es.onerror = () => {
      es.close();
      setIsLoading(false);
      setRunError("Connection lost or server error. Please try again.");
    };
  };

  const goNext = () => {
    if (currentTurn < totalTurns) {
      setShowDialogue(false);
      setTimeout(() => setCurrentTurn(prev => prev + 1), 300);
    }
  };

  const goPrev = () => {
    if (currentTurn > -1) {
      setShowDialogue(false);
      setTimeout(() => setCurrentTurn(prev => prev - 1), 300);
    }
  };

  const restart = () => {
    setShowDialogue(false);
    setCurrentTurn(-1);
    setIsAutoPlaying(false);
  };

  const currentData = storyData && currentTurn >= 0 && currentTurn < totalTurns ? storyData.turns[currentTurn] : null;
  const isConclusion = totalTurns > 0 && currentTurn >= totalTurns;
  const isOnLastTurnWhileStreaming = isLoading && totalTurns > 0 && currentTurn === totalTurns - 1;
  const isNextDisabled = isConclusion || isOnLastTurnWhileStreaming;

  return (
    <div className="min-h-screen bg-linear-to-br from-amber-100 via-orange-50 to-yellow-100">
      <div className="bg-linear-to-r from-amber-800 via-orange-700 to-red-800 text-white py-4 px-6 shadow-xl">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl md:text-4xl font-bold tracking-tight">{storyData?.title ?? "The Rickshaw Accident"}</h1>
          <p className="text-amber-200 text-sm md:text-base mt-1">Shahrah-e-Faisal, Karachi</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-4 md:p-6">
        <div className="relative rounded-2xl overflow-hidden shadow-2xl bg-white">
          <div className="relative h-125 md:h-150 overflow-hidden">
            <img 
              src={currentTurn % 2 === 0 ? sceneBackgrounds.main : sceneBackgrounds.alternate}
              alt="Scene"
              className="absolute inset-0 w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-linear-to-t from-black/70 via-black/20 to-transparent" />

            <AnimatePresence>
              {(!storyData || (storyData.turns?.length === 0 && !isLoading)) && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center p-6"
                >
                  <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-8 max-w-2xl shadow-2xl border border-amber-200">
                    <h2 className="text-3xl font-bold text-amber-900 mb-4">Start Story</h2>
                    <p className="text-gray-700 text-lg leading-relaxed mb-4">
                      Run the full narrative once. This may take a few minutes.
                    </p>
                    {runError && (
                      <p className="text-red-600 text-sm mb-4">{runError}</p>
                    )}
                    <div className="mt-6 flex gap-4 justify-center">
                      <Button 
                        onClick={startStory}
                        disabled={isLoading}
                        className="bg-linear-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white px-8 py-3 text-lg disabled:opacity-60"
                      >
                        {isLoading ? "Running story�" : "Start story"}
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {storyData && storyData.turns.length === 0 && isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center p-6"
                >
                  <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-8 max-w-2xl shadow-2xl border border-amber-200">
                    <h2 className="text-3xl font-bold text-amber-900 mb-4">Streaming story</h2>
                    <p className="text-gray-700 text-lg leading-relaxed">Waiting for first turn� (reviewed turns will appear here.)</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <AnimatePresence>
              {storyData && storyData.turns.length > 0 && currentTurn === -1 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center p-6"
                >
                  <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-8 max-w-2xl shadow-2xl border border-amber-200">
                    <h2 className="text-3xl font-bold text-amber-900 mb-4">Scene Setting</h2>
                    <p className="text-gray-700 text-lg leading-relaxed">{storyData.scenario}</p>
                    <div className="mt-6 flex gap-4 justify-center">
                      <Button 
                        onClick={goNext}
                        className="bg-linear-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white px-8 py-3 text-lg"
                      >
                        <Play className="w-5 h-5 mr-2" />
                        Begin Story
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence mode="wait">
              {currentData && (
                <motion.div
                  key={currentTurn}
                  initial={{ opacity: 0, x: -50 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 50 }}
                  transition={{ duration: 0.5 }}
                  className="absolute bottom-0 left-0 right-0 flex items-end justify-between p-4 md:p-8"
                >
                  <motion.div 
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.2, duration: 0.5 }}
                    className="relative"
                  >
                    <img 
                      src={characterImages[currentData.character]}
                      alt={currentData.speaker}
                      className="h-48 md:h-72 object-contain drop-shadow-2xl"
                    />
                    <div className={`absolute -top-2 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-linear-to-r ${characterColors[currentData.character].bg} text-white text-sm font-semibold shadow-lg whitespace-nowrap`}>
                      {currentData.speaker}
                    </div>
                  </motion.div>

                  <AnimatePresence>
                    {showDialogue && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.8, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        transition={{ duration: 0.4 }}
                        className="flex-1 ml-4 md:ml-8 mb-8"
                      >
                        <div className={`relative ${characterColors[currentData.character].bubble} border-2 rounded-2xl p-4 md:p-6 shadow-xl max-w-xl`}>
                          {/* Speech bubble tail */}
                          <div className={`absolute -left-3 bottom-8 w-6 h-6 ${characterColors[currentData.character].bubble} border-l-2 border-b-2 transform rotate-45`} />
                          
                          <p className={`text-sm md:text-base leading-relaxed ${characterColors[currentData.character].text}`}>
                            {currentData.dialogue.split('\n').map((line, i) => (
                              <span key={i}>
                                {line}
                                {i < currentData.dialogue.split('\n').length - 1 && <><br /><br /></>}
                              </span>
                            ))}
                          </p>
                          {currentData.actionText && (
                            <p className="mt-2 text-xs italic opacity-90">{currentData.actionText}</p>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {isConclusion && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center p-6"
                >
                  <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-8 max-w-3xl shadow-2xl border border-amber-200">
                    <h2 className="text-3xl font-bold text-amber-900 mb-4 text-center">The End</h2>
                    <p className="text-gray-700 text-base md:text-lg leading-relaxed italic">{storyData?.conclusion ?? ""}</p>
                    <div className="mt-6 flex justify-center">
                      <Button 
                        onClick={restart}
                        className="bg-linear-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 text-white px-8 py-3"
                      >
                        <RotateCcw className="w-5 h-5 mr-2" />
                        Watch Again
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {currentData && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-linear-to-r from-gray-900 to-gray-800 text-white p-4 md:p-6"
            >
              <div className="flex items-start gap-3">
                <div className="bg-amber-500 text-black text-xs font-bold px-2 py-1 rounded uppercase tracking-wider shrink-0">
                  Director
                </div>
                <p className="text-gray-300 text-sm md:text-base leading-relaxed italic">
                  {currentData.narration}
                </p>
              </div>
            </motion.div>
          )}

          {storyData && (
            <div className="bg-linear-to-r from-amber-900 to-orange-900 p-4 flex items-center justify-between">
              <Button
                onClick={goPrev}
                disabled={currentTurn <= -1}
                variant="ghost"
                className="text-white hover:bg-white/20 disabled:opacity-30"
              >
                <ChevronLeft className="w-6 h-6" />
                <span className="hidden md:inline ml-2">Previous</span>
              </Button>

              <div className="flex items-center gap-4">
                <div className="text-white/80 text-sm">
                  {currentTurn === -1 ? 'Intro' : isConclusion ? 'Conclusion' : `Turn ${currentTurn + 1} of ${totalTurns}`}
                </div>
                
                {!isConclusion && currentTurn >= 0 && (
                  <Button
                    onClick={() => setIsAutoPlaying(!isAutoPlaying)}
                    variant="ghost"
                    className={`text-white hover:bg-white/20 ${isAutoPlaying ? 'bg-white/20' : ''}`}
                  >
                    {isAutoPlaying ? <Volume2 className="w-5 h-5 animate-pulse" /> : <Play className="w-5 h-5" />}
                  </Button>
                )}

                <Button
                  onClick={restart}
                  variant="ghost"
                  className="text-white hover:bg-white/20"
                >
                  <RotateCcw className="w-5 h-5" />
                </Button>
              </div>

              <Button
                onClick={goNext}
                disabled={isNextDisabled}
                variant="ghost"
                className="text-white hover:bg-white/20 disabled:opacity-30"
              >
                <span className="hidden md:inline mr-2">Next</span>
                <ChevronRight className="w-6 h-6" />
              </Button>
            </div>
          )}
        </div>

        {storyData && (
          <>
            <div className="mt-4 bg-white/50 rounded-full h-2 overflow-hidden">
              <motion.div
                className="h-full bg-linear-to-r from-amber-500 to-orange-500"
                initial={{ width: 0 }}
                animate={{ width: `${((currentTurn + 2) / (totalTurns + 2)) * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>

            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(characterNames).map(([key, name]) => (
                <div 
                  key={key}
                  className={`flex items-center gap-3 bg-white rounded-xl p-3 shadow-md border border-gray-200 ${currentData?.character === key ? 'ring-2 ring-amber-500' : ''}`}
                >
                  <div className="w-14 h-14 shrink-0 rounded-lg overflow-hidden bg-gray-50 flex items-center justify-center">
                    <img 
                      src={characterImages[key]} 
                      alt={name}
                      className="w-full h-full object-contain object-center"
                    />
                  </div>
                  <span className="text-xs md:text-sm font-medium text-gray-700">{name}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}