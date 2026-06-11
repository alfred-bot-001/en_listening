import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-16 text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          🎧 ListenFlow
        </h1>
        <p className="text-lg text-gray-600 mb-12">
          English Listening Practice - Dictation & Fill-in-the-blank
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mx-auto">
          <Link
            href="/materials"
            className="bg-white rounded-lg shadow-sm p-8 hover:shadow-md transition-shadow"
          >
            <div className="text-3xl mb-3">📚</div>
            <h2 className="text-xl font-semibold text-gray-900">Materials</h2>
            <p className="text-gray-500 mt-1">
              Import videos, audio, YouTube & Bilibili
            </p>
          </Link>
          <Link
            href="/practice"
            className="bg-white rounded-lg shadow-sm p-8 hover:shadow-md transition-shadow"
          >
            <div className="text-3xl mb-3">✍️</div>
            <h2 className="text-xl font-semibold text-gray-900">Practice</h2>
            <p className="text-gray-500 mt-1">
              Dictation & fill-in-the-blank exercises
            </p>
          </Link>
          <Link
            href="/favorites"
            className="bg-white rounded-lg shadow-sm p-8 hover:shadow-md transition-shadow"
          >
            <div className="text-3xl mb-3">★</div>
            <h2 className="text-xl font-semibold text-gray-900">Favorites</h2>
            <p className="text-gray-500 mt-1">
              Your saved sentences for review
            </p>
          </Link>
          <Link
            href="/wrongbook"
            className="bg-white rounded-lg shadow-sm p-8 hover:shadow-md transition-shadow"
          >
            <div className="text-3xl mb-3">✗</div>
            <h2 className="text-xl font-semibold text-gray-900">
              Wrong Book
            </h2>
            <p className="text-gray-500 mt-1">
              Sentences you got wrong 3+ times
            </p>
          </Link>
        </div>
      </div>
    </div>
  );
}
