export default function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-8">
      <div className="w-full max-w-5xl bg-white rounded-3xl shadow-xl p-10">

        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-5xl font-bold text-gray-800 mb-3">
            AI Order Automation Assistant
          </h1>

          <p className="text-gray-600 text-lg">
            Upload customer orders, review them, and automatically place orders
            on your website.
          </p>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-6 mb-10">

          <div className="bg-gray-50 rounded-2xl p-6 shadow-sm">
            <h2 className="text-xl font-semibold mb-3">
              📄 Upload Orders
            </h2>

            <p className="text-gray-600">
              Import customer orders from PDF files and extract all information
              automatically.
            </p>
          </div>

          <div className="bg-gray-50 rounded-2xl p-6 shadow-sm">
            <h2 className="text-xl font-semibold mb-3">
              ✏️ Review & Edit
            </h2>

            <p className="text-gray-600">
              Verify products, colors, sizes, quantities, and customer details
              before processing.
            </p>
          </div>

          <div className="bg-gray-50 rounded-2xl p-6 shadow-sm">
            <h2 className="text-xl font-semibold mb-3">
              🤖 Website Automation
            </h2>

            <p className="text-gray-600">
              Automatically search products, add items to cart, fill checkout
              information, and complete orders.
            </p>
          </div>

        </div>

        {/* Statistics */}
        <div className="grid grid-cols-3 gap-6 mb-10">

          <div className="bg-blue-50 rounded-2xl p-6 text-center">
            <h3 className="text-3xl font-bold text-blue-600">0</h3>
            <p className="text-gray-600 mt-2">Orders Loaded</p>
          </div>

          <div className="bg-green-50 rounded-2xl p-6 text-center">
            <h3 className="text-3xl font-bold text-green-600">0</h3>
            <p className="text-gray-600 mt-2">Completed</p>
          </div>

          <div className="bg-red-50 rounded-2xl p-6 text-center">
            <h3 className="text-3xl font-bold text-red-600">0</h3>
            <p className="text-gray-600 mt-2">Failed</p>
          </div>

        </div>

        {/* Buttons */}
        <div className="flex justify-center gap-4">

          <button
            className="bg-blue-600 text-white px-8 py-3 rounded-xl font-semibold hover:bg-blue-700 transition"
          >
            Upload PDF
          </button>

          <button
            className="bg-gray-200 text-gray-700 px-8 py-3 rounded-xl font-semibold hover:bg-gray-300 transition"
          >
            View Orders
          </button>

        </div>

      </div>
    </div>
  );
}